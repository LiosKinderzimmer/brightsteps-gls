from frappe.model.document import Document
import frappe


class GLSSettings(Document):
    def validate(self):
        allowed = {
            "sandbox_auth_url": "https://api-sandbox.gls-group.net/oauth2/v2/token",
            "sandbox_api_url": "https://api-sandbox.gls-group.net/shipit-farm/v1/backend",
            "production_auth_url": "https://api.gls-group.net/oauth2/v2/token",
            "production_api_url": "https://api.gls-group.net/shipit-farm/v1/backend",
        }
        for field, value in allowed.items():
            self.set(field, value)
        if self.environment == "Production" and not self.production_approved:
            frappe.throw("Der Produktivbetrieb muss nach der schriftlichen GLS-Freigabe ausdrücklich genehmigt werden.")
