from odoo import models, fields

class Property(models.Model):
    _name = "estate.property"
    _description = "Estate properties"
    name = fields.Char(string='name'required=True )
    description = fields.Char(string='description')
    postcode = fields.Char(string='postcode')
    date_availability = fields.Date(string="Available From")
    expected_price = fields.Float(string="Expected Price")
    best_offer = fields.Float(string="Best Offer")
    selling_price = fields.Float(string="Selling Price")
    bedrooms = fields.Integer(string="Bedrooms")
    living_rooms = fields.Integer(string="Living Rooms")
    facades = fields.Integer(string="Facades")
    garage = fields.Boolean(string="Garage")
    garden = fields.Boolean(string="Garden")
    garden_area = fields.Integer(string="Garden area")
    garden_orientation = fields.Selection(
        [("north", "North"), ("south", "South"), ("east", "East"), ("west", "West")],
        string="Garden orientation" default="north",
    )
    id,create_date,create_vid,write_date,write_vid