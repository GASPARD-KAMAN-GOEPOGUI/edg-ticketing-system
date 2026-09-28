"""
Barrel export — tous les routers EDG Support.
Convention de nommage : Route{Domaine}.py
"""
from api.routes.health import router as health_router
from api.routes.RouteAuth import router as auth_router
from api.routes.RouteReferences import router as references_router
from api.routes.RouteUnity import router as unity_router
from api.routes.RouteOrganigram import router as organigram_router
from api.routes.RouteDirectionsUnits import directions_router, departments_router, units_router, public_dirs_router
from api.routes.RouteAccount import router as account_router
from api.routes.RouteRequest import router as request_router
from api.routes.RouteRequest import public_router as public_request_router
from api.routes.RouteAttachment import router as attachment_router
from api.routes.RouteSlaPolicy import router as sla_policy_router
from api.routes.RouteSlaPolicy import read_router as sla_policy_read_router
from api.routes.RouteRoutingRule import router as routing_rule_router
from api.routes.RouteWorkflow import router as workflow_router
from api.routes.RouteWorkflow import request_workflow_router
from api.routes.RouteWorkflow import workflow_detail_router
from api.routes.RouteTask import router as task_router
from api.routes.RouteNotification import router as notification_router
from api.routes.RouteActivityLog import router as activity_log_router
from api.routes.RouteAppreciation import router as appreciation_router
from api.routes.RouteRequestAppreciation import router as request_appreciation_router
from api.routes.RouteCsatStats import router as csat_stats_router
from api.routes.RouteAdminConfig import router as admin_config_router
from api.routes.RouteUsers import router as users_router
from api.routes.RouteUsers import me_router as users_me_router
from api.routes.RouteUsers import avatars_router as users_avatars_router
from api.routes.RouteUsers import staff_router as users_staff_router
from api.routes.RouteStats import router as stats_router
from api.routes.RouteStats import agent_router as agent_stats_router
from api.routes.RouteReports import router as reports_router
from api.routes.RouteSSE import router as sse_router

__all__ = [
    "health_router", "auth_router", "references_router",
    "unity_router", "organigram_router", "directions_router",
    "departments_router", "units_router", "public_dirs_router",
    "account_router", "request_router", "public_request_router",
    "attachment_router", "sla_policy_router", "sla_policy_read_router",
    "routing_rule_router", "workflow_router",
    "request_workflow_router", "workflow_detail_router", "task_router",
    "notification_router", "activity_log_router", "appreciation_router",
    "request_appreciation_router", "csat_stats_router", "admin_config_router", "users_router", "users_me_router",
    "users_avatars_router", "users_staff_router", "stats_router",
    "agent_stats_router", "reports_router", "sse_router",
]
