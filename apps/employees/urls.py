"""Routes for the employees app, mounted under /api/v1."""

from rest_framework.routers import SimpleRouter

from apps.employees.views import EmployeeViewSet

# SimpleRouter rather than DefaultRouter: three apps are included at the same
# prefix, and DefaultRouter's API-root view would collide between them.
router = SimpleRouter()
router.register("employees", EmployeeViewSet, basename="employee")

urlpatterns = router.urls
