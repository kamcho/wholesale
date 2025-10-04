from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from .services import gavaconnect


def health(request):
    """Basic health endpoint for the core app."""
    return JsonResponse({"status": "ok"})


@csrf_exempt  # Consider removing once called from your own frontend with CSRF token
@require_POST
def gava_pin_check(request: HttpRequest) -> JsonResponse:
    """Proxy endpoint to GavaConnect PIN Checker by ID.

    Expected JSON body: { "TaxpayerType": "KE", "TaxpayerID": "41789723" }
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            # Fallback to form data
            payload = {
                'TaxpayerType': request.POST.get('TaxpayerType'),
                'TaxpayerID': request.POST.get('TaxpayerID'),
            }
        ttype = (payload.get('TaxpayerType') or '').strip()
        tid = (payload.get('TaxpayerID') or '').strip()
        # Debug print: show submitted values in server console
        print(f"[Gava PIN API] Submitted TaxpayerType={ttype!r} TaxpayerID={tid!r}")
        if not ttype or not tid:
            return JsonResponse({
                'error': 'Missing parameters',
                'details': 'TaxpayerType and TaxpayerID are required.'
            }, status=400)

        data = gavaconnect.pin_check_by_id(ttype, tid)
        # If API responds with known error structure, set appropriate status
        if isinstance(data, dict) and (
            'ErrorCode' in data or 'errorCode' in data
        ):
            return JsonResponse(data, status=400)
        return JsonResponse(data, status=200)
    except gavaconnect.GavaConnectError as e:
        return JsonResponse({'error': 'GavaConnectError', 'details': str(e)}, status=502)
    except Exception as e:
        return JsonResponse({'error': 'ServerError', 'details': str(e)}, status=500)


def pin_check_form(request: HttpRequest):
    """Simple UI to test GavaConnect PIN Checker."""
    context = {
        'result': None,
        'error': None,
        'batch': None,
        'TaxpayerType': request.POST.get('TaxpayerType', 'KE') if request.method == 'POST' else 'KE',
        'TaxpayerID': request.POST.get('TaxpayerID', '') if request.method == 'POST' else '',
    }
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()
        if action == 'testall':
            # Run documented sample cases
            samples = [
                ('KE', '41789723', 'Kenyan Resident'),
                ('NKE', '787528', 'Non Kenyan Resident'),
                ('NKENR', 'B3962C4A5718', 'Non-Kenyan Non-Resident'),
                ('COMP', '0000200S4304', 'Company'),
            ]
            batch_results = []
            from .services.gavaconnect import check_pin
            for ttype_s, tid_s, label in samples:
                try:
                    print(f"[Gava PIN FORM][TESTALL] {label}: TaxpayerType={ttype_s!r} TaxpayerID={tid_s!r}")
                    data = check_pin(ttype_s, tid_s)
                    batch_results.append({
                        'label': label,
                        'TaxpayerType': ttype_s,
                        'TaxpayerID': tid_s,
                        'response': data,
                    })
                except Exception as e:
                    batch_results.append({
                        'label': label,
                        'TaxpayerType': ttype_s,
                        'TaxpayerID': tid_s,
                        'response': {'error': str(e)},
                    })
            context['batch'] = batch_results
        else:
            ttype = (request.POST.get('TaxpayerType') or '').strip()
            tid = (request.POST.get('TaxpayerID') or '').strip()
            # Debug print: show submitted values in server console
            print(f"[Gava PIN FORM] Submitted TaxpayerType={ttype!r} TaxpayerID={tid!r}")
            if not ttype or not tid:
                context['error'] = 'TaxpayerType and TaxpayerID are required.'
            else:
                try:
                    from .services.gavaconnect import check_pin
                    data = check_pin(ttype, tid)
                    # If upstream provides error json, surface it
                    if isinstance(data, dict) and ('ErrorCode' in data or 'errorCode' in data):
                        context['error'] = data
                    else:
                        context['result'] = data
                except Exception as e:
                    context['error'] = str(e)
    return render(request, 'core/pin_check.html', context)


@csrf_exempt  # Consider removing once called from your own frontend with CSRF token
@require_POST
def gava_pending_returns(request: HttpRequest) -> JsonResponse:
    """Pending Returns API proxy.

    Expected JSON body: { "taxPayerPin": "A000000000L", "obligationId": "4" }
    """
    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = {
                'taxPayerPin': request.POST.get('taxPayerPin'),
                'obligationId': request.POST.get('obligationId'),
            }
        pin = (payload.get('taxPayerPin') or '').strip().upper()
        obl = str(payload.get('obligationId') or '').strip()
        print(f"[Gava PENDING API] taxPayerPin={pin!r} obligationId={obl!r}")
        if not pin or not obl:
            return JsonResponse({'error': 'Missing parameters', 'details': 'taxPayerPin and obligationId are required.'}, status=400)
        data = gavaconnect.pending_returns(pin, obl)
        # Upstream responds 200 with RESULT or error payload; pass through as 200
        return JsonResponse(data, status=200)
    except gavaconnect.GavaConnectError as e:
        return JsonResponse({'error': 'GavaConnectError', 'details': str(e)}, status=502)
    except Exception as e:
        return JsonResponse({'error': 'ServerError', 'details': str(e)}, status=500)


def pending_returns_form(request: HttpRequest):
    """Simple UI to test Pending Returns by PIN & obligation."""
    context = {
        'result': None,
        'error': None,
        'taxPayerPin': request.POST.get('taxPayerPin', '') if request.method == 'POST' else '',
        'obligationId': request.POST.get('obligationId', '7') if request.method == 'POST' else '7',
    }
    if request.method == 'POST':
        pin = (request.POST.get('taxPayerPin') or '').strip().upper()
        obl = str(request.POST.get('obligationId') or '').strip()
        print(f"[Gava PENDING FORM] taxPayerPin={pin!r} obligationId={obl!r}")
        if not pin or not obl:
            context['error'] = 'taxPayerPin and obligationId are required.'
        else:
            try:
                from .services.gavaconnect import pending_returns
                data = pending_returns(pin, obl)
                context['result'] = data
            except Exception as e:
                context['error'] = str(e)
    return render(request, 'core/pending_returns.html', context)


@csrf_exempt  # Consider removing once called from your own frontend with CSRF token
@require_POST
def gava_token(request: HttpRequest) -> JsonResponse:
    """Generate and return a GavaConnect access token.

    Returns: { "access_token": str, "expires_in": int }
    """
    try:
        token, expires_in = gavaconnect.get_access_token()
        return JsonResponse({
            'access_token': token,
            'expires_in': expires_in,
        })
    except gavaconnect.GavaConnectError as e:
        return JsonResponse({'error': 'GavaConnectError', 'details': str(e)}, status=502)
    except Exception as e:
        return JsonResponse({'error': 'ServerError', 'details': str(e)}, status=500)
