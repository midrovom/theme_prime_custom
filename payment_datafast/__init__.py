from . import controllers
from . import models
from . import wizard

from odoo.addons.payment import setup_provider, reset_payment_provider

# def post_init_hook(env):
#     setup_provider(env, 'datafast')

# def uninstall_hook(env):
#     reset_payment_provider(env, 'datafast')


def post_init_hook(cr, registry):
    setup_provider(cr, registry, 'datafast')


def uninstall_hook(cr, registry):
    reset_payment_provider(cr, registry, 'datafast')