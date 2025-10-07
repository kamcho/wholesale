# M-Pesa Production Setup Guide

## 1. Get Production Credentials from Safaricom

1. Go to https://developer.safaricom.co.ke/
2. Create an account and log in
3. Create a new app or use existing app
4. Get your production credentials:
   - Consumer Key
   - Consumer Secret  
   - Business Shortcode (your paybill number)
   - Passkey (from your app settings)

## 2. Update .env file

Replace the placeholder values in .env with your actual production credentials:

```
MPESA_CONSUMER_KEY=your_actual_consumer_key
MPESA_CONSUMER_SECRET=your_actual_consumer_secret
MPESA_BUSINESS_SHORTCODE=your_actual_business_shortcode
MPESA_PASSKEY=your_actual_passkey
MPESA_CALLBACK_URL=https://yourdomain.com/api/mpesa-callback/
```

## 3. Important Notes

- Use HTTPS for callback URL in production
- Test with small amounts first
- Keep credentials secure
- Monitor transactions in Safaricom dashboard

## 4. Test the Setup

1. Restart your Django server
2. Try a test payment
3. Check server logs for any errors

## Current Status

✅ M-Pesa service configured for production
✅ Error handling improved
✅ Credentials validation added
⚠️  Replace placeholder credentials with real ones
