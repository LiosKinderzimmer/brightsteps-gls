import json
from urllib.parse import quote

import frappe


SUCCESSFUL_CANCELLATIONS = {"CANCELLED", "CANCELLATION_PENDING"}
HANDED_OVER_STATUSES = {"PICKUP", "HUB", "IN_DELIVERY", "DELIVERED"}


class GLSClient:
    def __init__(self, settings=None):
        self.settings = settings or frappe.get_single("GLS Settings")
        self._token = None
        if not self.settings.enabled:
            frappe.throw("GLS ist nicht aktiviert.")

    @property
    def auth_url(self):
        return self.settings.sandbox_auth_url if self.settings.environment == "Sandbox" else self.settings.production_auth_url

    @property
    def api_url(self):
        return self.settings.sandbox_api_url if self.settings.environment == "Sandbox" else self.settings.production_api_url

    def token(self):
        if self._token:
            return self._token
        production = self.settings.environment == "Production"
        client_id = self.settings.production_client_id if production else self.settings.sandbox_client_id
        secret_field = "production_client_secret" if production else "sandbox_client_secret"
        secret = self.settings.get_password(secret_field)
        if production and not self.settings.production_approved:
            frappe.throw("Produktivbetrieb ist nicht freigegeben.")
        if not client_id or not secret:
            frappe.throw("GLS-Zugangsdaten für die gewählte Umgebung fehlen.")
        response = frappe.make_post_request(
            self.auth_url,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
            headers={"Accept": "application/json"},
        )
        self._token = response.get("access_token")
        if not self._token:
            frappe.throw("GLS hat kein Zugangstoken ausgegeben.")
        return self._token

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/glsVersion1+json",
            "Accept": "application/glsVersion1+json",
        }

    def post(self, path, payload=None):
        return frappe.make_post_request(
            f"{self.api_url.rstrip('/')}/{path.lstrip('/')}",
            data=json.dumps(payload) if payload is not None else "",
            headers=self.headers(),
        )

    def validate(self, shipment):
        response = self.post("rs/shipments/validate", {"Shipment": shipment})
        result = response.get("ValidateParcelsResponse", response)
        return result.get("success", result.get("Success")) is True, result

    def create(self, shipment):
        response = self.post("rs/shipments", {
            "Shipment": shipment,
            "PrintingOptions": {"ReturnLabels": {"LabelFormat": "PDF", "TemplateSet": "NONE"}},
        })
        return response.get("CreateParcelsResponse", response).get("CreatedShipment", {})

    def cancel(self, track_id):
        if not track_id or not track_id.isalnum():
            frappe.throw("Ungültige GLS Track ID.")
        response = self.post(f"rs/shipments/cancel/{quote(track_id, safe='')}")
        result = response.get("CancelParcelResponse", response)
        return result.get("TrackID"), result.get("Result") or result.get("result")

    def tracking(self, shipment_reference, date_from, date_to):
        response = self.post("rs/tracking/parcels", {
            "ShipmentReference": shipment_reference,
            "DateFrom": str(date_from),
            "DateTo": str(date_to),
        })
        return response.get("TUListResponse", response).get("UnitItems", [])
