from django.contrib import admin
from .models import (
    Product,
    ProductCategory,
    Business,
    ProductImage,
    BusinessCategory,
    ProductCategoryFilter,
    ProductReview,
    ProductReviewImage,
    ProductVariation,
    PriceTier,
    ProductOrder,
    ProductAttribute,
    ProductAttributeValue,
    ProductAttributeAssignment,PromiseFee,ProductKB, ServiceCategory,Agent, AgentImage, AgentReview, AgentAIKnowledgeBase, ExchangeRate)

admin.site.register(PromiseFee)
admin.site.register(ServiceCategory)
admin.site.register(Agent)
admin.site.register(ExchangeRate)
class ProductVariationInline(admin.TabularInline):
    model = ProductVariation
    extra = 1
    fields = ("name", "moq", "price")
admin.site.register(ProductKB)
admin.site.register(AgentImage)
admin.site.register(AgentReview)
admin.site.register(AgentAIKnowledgeBase)
class ProductImageInlineForProduct(admin.TabularInline):
    model = ProductImage
    fk_name = "product"
    extra = 1
    fields = ("image", "caption", "is_default")
    exclude = ("variation",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "moq")
    inlines = [ProductVariationInline, ProductImageInlineForProduct]


class ProductImageInlineForVariation(admin.TabularInline):
    model = ProductImage
    fk_name = "variation"
    extra = 1
    fields = ("image", "caption", "is_default")
    exclude = ("product",)


class PriceTierInline(admin.TabularInline):
    model = PriceTier
    extra = 1
    fields = ("min_quantity", "max_quantity", "price")


@admin.register(ProductVariation)
class ProductVariationAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "moq", "price")
    inlines = [ProductImageInlineForVariation, PriceTierInline]


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1
    fields = ("value",)


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    inlines = [ProductAttributeValueInline]


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value", "created_at")
    list_filter = ("attribute", "created_at")
    search_fields = ("value", "attribute__name")


@admin.register(ProductAttributeAssignment)
class ProductAttributeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("product", "value", "created_at")
    list_filter = ("value__attribute", "created_at")
    search_fields = ("product__name", "value__value", "value__attribute__name")


@admin.register(PriceTier)
class PriceTierAdmin(admin.ModelAdmin):
    list_display = ("variation", "min_quantity", "max_quantity", "price")
    list_filter = ("variation__product",)
    search_fields = ("variation__product__name", "variation__name")


admin.site.register(ProductCategory)
admin.site.register(Business)
admin.site.register(ProductImage)
admin.site.register(BusinessCategory)
admin.site.register(ProductCategoryFilter)
admin.site.register(ProductReview)
admin.site.register(ProductReviewImage)
admin.site.register(ProductOrder)
