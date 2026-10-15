from django.urls import path
from core import views as v, simple as s
urlpatterns=[
 path('w/<uuid:division_id>/',s.dashboard,name='dashboard'),
 path('w/<uuid:division_id>/opening-balance/',s.opening_balance,name='simple_opening_balance'),
 path('w/<uuid:division_id>/transactions/',s.transactions,name='simple_transactions'),
 path('w/<uuid:division_id>/transactions/new/',s.transaction_form,name='simple_transaction_new'),
 path('w/<uuid:division_id>/transactions/<uuid:entry_id>/',s.transaction_detail,name='simple_transaction_detail'),
 path('w/<uuid:division_id>/transactions/<uuid:entry_id>/edit/',s.transaction_form,name='simple_transaction_edit'),
 path('w/<uuid:division_id>/calculator/',s.calculator,name='simple_calculator'),
 path('w/<uuid:division_id>/decisions/',s.decisions,name='simple_decisions'),
 path('w/<uuid:division_id>/decisions/add/',s.decision_new,name='simple_decision_new'),
 path('w/<uuid:division_id>/decisions/review/<uuid:decision_id>/',s.decision_detail,name='simple_decision_detail'),
 path('w/<uuid:division_id>/decisions/review/<uuid:decision_id>/action/',s.decision_action,name='simple_decision_action'),
 path('w/<uuid:division_id>/documents/',s.documents,name='simple_documents'),
 path('w/<uuid:division_id>/documents/<uuid:document_id>/view/',s.document_preview,name='simple_document_preview'),
 path('w/<uuid:division_id>/reports/',s.reports_view,name='simple_reports'),
 path('w/<uuid:division_id>/reports/export/<str:kind>/',s.export_view,name='simple_export'),
 path('w/<uuid:division_id>/repayment-proposal/',v.repayment_proposal,name='repayment_proposal'),path('',v.home,name='home'),path('health/',v.health,name='health'),path('login/',v.login_view,name='login'),path('logout/',v.logout_view,name='logout'),path('enroll/<str:token>/',v.enroll,name='enroll'),path('security/mfa/',v.mfa,name='mfa'),path('security/reauth/',v.reauth,name='reauth'),path('w/<uuid:division_id>/sections/<str:section>/',v.page,name='page'),path('w/<uuid:division_id>/records/new/',v.fact_new,name='fact_new'),path('w/<uuid:division_id>/records/<uuid:record_id>/',v.record_detail,name='record'),path('w/<uuid:division_id>/decisions/new/',v.decision_form,name='decision_new'),path('w/<uuid:division_id>/decisions/<uuid:decision_id>/edit/',v.decision_form,name='decision_edit'),path('w/<uuid:division_id>/decisions/<uuid:decision_id>/',v.decision_detail,name='decision'),path('w/<uuid:division_id>/decisions/<uuid:decision_id>/<str:action>/',v.decision_action,name='decision_action'),path('api/w/<uuid:division_id>/decisions/<uuid:decision_id>/<str:action>/',v.api_decision,name='api_decision'),path('w/<uuid:division_id>/scenario/',v.scenario_view,name='scenario'),path('w/<uuid:division_id>/documents/upload/',v.document_upload,name='upload'),path('w/<uuid:division_id>/documents/<uuid:document_id>/',v.download,name='download'),path('w/<uuid:division_id>/contracts/<uuid:contract_id>/',v.contract_view,name='contract'),path('w/<uuid:division_id>/contracts/<uuid:contract_id>/pdf/',v.contract_pdf,name='contract_pdf'),path('w/<uuid:division_id>/contracts/<uuid:contract_id>/evidence/',v.contract_evidence,name='contract_evidence'),path('w/<uuid:division_id>/bank/import/',v.bank_import,name='bank_import'),path('w/<uuid:division_id>/bank/match/',v.bank_match,name='bank_match'),path('w/<uuid:division_id>/search/',v.search,name='search'),path('w/<uuid:division_id>/exports/<str:format>/',v.export,name='export')]
