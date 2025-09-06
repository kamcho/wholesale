from django.contrib import admin
from .models import Product, ProductCategory, Business, ProductImage, BusinessCategory, ProductCategoryFilter, ProductReview, ProductReviewImage, ProductVariation

admin.site.register(Product)
admin.site.register(ProductCategory)
admin.site.register(Business)
admin.site.register(ProductImage)
admin.site.register(BusinessCategory)
admin.site.register(ProductCategoryFilter)
admin.site.register(ProductReview)
admin.site.register(ProductReviewImage)
admin.site.register(ProductVariation)   
# Register your models here.
