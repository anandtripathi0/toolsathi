from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from apps.core import views as core
from apps.tools import views as tools
from apps.accounts import views as accounts
from apps.downloads import views as downloads
from apps.seo import views as seo

urlpatterns = [path('', core.home, name='home'), path('tools/', tools.directory, name='tools'),
    path('category/<slug:category_id>/', tools.directory, name='category'), path('tools/<slug:slug>/', tools.detail, name='tool'),
    path('api/search/', tools.search, name='search'), path('search/', tools.search_partial, name='search_partial'),
    path('api/tools/<slug:slug>/process/', tools.process, name='process'), path('api/preferences/', accounts.preferences, name='preferences'),
    path('accounts/login/', auth.LoginView.as_view(), name='login'), path('accounts/logout/', auth.LogoutView.as_view(), name='logout'),
    path('accounts/signup/', accounts.signup, name='signup'), path('accounts/dashboard/', accounts.dashboard, name='dashboard'),
    path('download-app/', downloads.app, name='download_app'), path('downloads/toolsathi-latest.apk', downloads.apk_download, name='apk_download'),
    path('downloads/results/<str:token>/', downloads.result_download, name='result_download'),
    path('privacy/', core.static_page, {'page': 'privacy'}, name='privacy'), path('about/', core.static_page, {'page': 'about'}, name='about'),
    path('offline/', core.static_page, {'page': 'offline'}, name='offline'), path('health/', core.health, name='health'),
    path('manifest.webmanifest', core.manifest, name='manifest'), path('sw.js', core.service_worker, name='service_worker'),
    path('sitemap.xml', seo.sitemap, name='sitemap'), path('robots.txt', seo.robots, name='robots'), path('admin/', admin.site.urls)]
