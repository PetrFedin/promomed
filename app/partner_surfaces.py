"""Composition router for versioned partner-facing product surfaces."""
from app import partner_appointments, partner_commercial, organization_operations


def serve(actor, raw_path):
    path = raw_path.split("?", 1)[0].split("#", 1)[0]
    if path == organization_operations.ROUTE:
        return organization_operations.serve(actor,raw_path)
    if path == partner_commercial.ROUTE:
        return partner_commercial.serve(actor, raw_path)
    if path in (partner_appointments.ROUTE,partner_appointments.AVAILABLE_ROUTE):
        return partner_appointments.serve(actor, raw_path)
    return None


def handle_command(c, route, role, email, data):
    result = partner_commercial.handle_command(c, route, role, email, data)
    if result is not None:
        return result
    return partner_appointments.handle_command(c, route, role, email, data)
