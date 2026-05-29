from odoo.exceptions import UserError


class DetrackUtility:
    @staticmethod
    def get_mapped_state(state):
        if state == 'completed':
            return 'done'
        elif state == 'failed':
            return 'cancel'
        elif state == 'completed_partial':
            return 'done'

        elif state == 'dispatched':
            # TODO : handle this case
            return None
        elif state == 'info_recv':
            # TODO : handle this case
            return None
        elif state == 'on_hold':
            # TODO : handle this case
            return None
        elif state == 'return':
            # TODO : handle this case
            return None
        else:
            raise UserError(f"Blanket order received an invalid state: {state}")

