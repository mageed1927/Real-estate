# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class HelpdeskPortalController(http.Controller):

    @http.route(['/my/ticket/stage/update'], type='http', auth="user", website=True)
    def helpdesk_ticket_change_stage(self, ticket_id, stage_id, access_token=None, **kw):
        """
        Controller to handle stage change from the portal.
        """
        try:
            ticket_id = int(ticket_id)
            stage_id = int(stage_id)
            ticket_sudo = request.env['helpdesk.ticket'].sudo().browse(ticket_id)
            ticket_sudo.check_access_rights('read')
            ticket_sudo.check_access_rule('read')
        except Exception:
            return request.redirect('/my/tickets')

        if stage_id not in ticket_sudo.team_id.stage_ids.ids:
            return request.redirect(ticket_sudo.get_portal_url())

        ticket_sudo.write({'stage_id': stage_id})

        return request.redirect(ticket_sudo.get_portal_url())