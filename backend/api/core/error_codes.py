"""
Codes d'erreur centralisés pour l'API EDG Connect.
Chaque code identifie de façon unique un type d'erreur métier
et peut être utilisé par le frontend pour afficher des messages localisés.
"""
from __future__ import annotations
from enum import Enum


class ErrorCode(str, Enum):

    # ── 404 Not Found ──────────────────────────────────────────────────────
    NOT_FOUND                = "NOT_FOUND"
    ACCOUNT_NOT_FOUND        = "ACCOUNT_NOT_FOUND"
    DIRECTION_NOT_FOUND      = "DIRECTION_NOT_FOUND"
    UNIT_NOT_FOUND           = "UNIT_NOT_FOUND"
    REQUEST_NOT_FOUND        = "REQUEST_NOT_FOUND"
    COMMENT_NOT_FOUND        = "COMMENT_NOT_FOUND"
    ESCALATION_NOT_FOUND     = "ESCALATION_NOT_FOUND"
    TASK_NOT_FOUND           = "TASK_NOT_FOUND"
    WORKFLOW_NOT_FOUND       = "WORKFLOW_NOT_FOUND"
    NOTIFICATION_NOT_FOUND   = "NOTIFICATION_NOT_FOUND"
    APPRECIATION_NOT_FOUND   = "APPRECIATION_NOT_FOUND"
    CATEGORY_NOT_FOUND       = "CATEGORY_NOT_FOUND"
    SLA_POLICY_NOT_FOUND     = "SLA_POLICY_NOT_FOUND"
    ROUTING_RULE_NOT_FOUND   = "ROUTING_RULE_NOT_FOUND"
    ANNOUNCEMENT_NOT_FOUND   = "ANNOUNCEMENT_NOT_FOUND"
    ARTICLE_NOT_FOUND        = "ARTICLE_NOT_FOUND"
    EMPLOYEE_NOT_FOUND       = "EMPLOYEE_NOT_FOUND"
    ATTACHMENT_NOT_FOUND     = "ATTACHMENT_NOT_FOUND"
    TIMELINE_NOT_FOUND       = "TIMELINE_NOT_FOUND"
    CONFIG_NOT_FOUND         = "CONFIG_NOT_FOUND"
    LOG_NOT_FOUND            = "LOG_NOT_FOUND"
    SLA_LEVEL_NOT_FOUND      = "SLA_LEVEL_NOT_FOUND"

    # ── 409 Conflict ───────────────────────────────────────────────────────
    EMAIL_ALREADY_EXISTS     = "EMAIL_ALREADY_EXISTS"
    MATRICULE_ALREADY_EXISTS = "MATRICULE_ALREADY_EXISTS"
    PHONE_ALREADY_EXISTS     = "PHONE_ALREADY_EXISTS"
    CODE_ALREADY_EXISTS      = "CODE_ALREADY_EXISTS"
    REF_ALREADY_EXISTS       = "REF_ALREADY_EXISTS"
    SLUG_ALREADY_EXISTS      = "SLUG_ALREADY_EXISTS"
    DUPLICATE_ENTRY          = "DUPLICATE_ENTRY"
    ALREADY_EXISTS           = "ALREADY_EXISTS"
    DUPLICATE_REQUEST        = "DUPLICATE_REQUEST"
    TICKET_STATE_CONFLICT    = "TICKET_STATE_CONFLICT"

    # ── 422 Unprocessable ──────────────────────────────────────────────────
    FOREIGN_KEY_VIOLATION    = "FOREIGN_KEY_VIOLATION"
    VALIDATION_ERROR         = "VALIDATION_ERROR"
    MISSING_REQUIRED_FIELD   = "MISSING_REQUIRED_FIELD"

    # ── 400 Bad Request ────────────────────────────────────────────────────
    INVALID_REQUEST          = "INVALID_REQUEST"
    INVALID_STATUS_TRANSITION= "INVALID_STATUS_TRANSITION"
    INVALID_FIELD_VALUE      = "INVALID_FIELD_VALUE"
    BUSINESS_RULE_VIOLATION  = "BUSINESS_RULE_VIOLATION"
    BUILTIN_PROTECTED        = "BUILTIN_PROTECTED"
    REQUESTER_CANNOT_TREAT_OWN_TICKET = "REQUESTER_CANNOT_TREAT_OWN_TICKET"

    # ── 403 / 401 ──────────────────────────────────────────────────────────
    FORBIDDEN                = "FORBIDDEN"
    UNAUTHORIZED             = "UNAUTHORIZED"
    INVALID_CREDENTIALS      = "INVALID_CREDENTIALS"
    ACCOUNT_DISABLED         = "ACCOUNT_DISABLED"
    RESET_CODE_INVALID       = "RESET_CODE_INVALID"
    RESET_CODE_EXPIRED       = "RESET_CODE_EXPIRED"

    # ── 429 Rate limit ─────────────────────────────────────────────────────
    RATE_LIMITED             = "RATE_LIMITED"

    # ── 500 Internal ───────────────────────────────────────────────────────
    DATABASE_ERROR           = "DATABASE_ERROR"
    INTERNAL_ERROR           = "INTERNAL_ERROR"
