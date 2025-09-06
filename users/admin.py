from django.contrib import admin
from .models import MyUser, PersonalProfile

@admin.register(MyUser)
class MyUserAdmin(admin.ModelAdmin):
    list_display = ('email',   'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

@admin.register(PersonalProfile)
class PersonalProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'phone', 'location', 'gender', 'created_at')
    list_filter = ('gender', 'created_at')
    search_fields = ('user__email', 'first_name', 'last_name', 'phone', 'location')
    ordering = ('-created_at',)


    list_display = ('user',  'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    ordering = ('-created_at',)
    
    readonly_fields = ('created_at',)
    
   