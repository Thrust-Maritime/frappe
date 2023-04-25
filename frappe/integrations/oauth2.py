import json
from urllib.parse import quote, urlencode

from oauthlib.oauth2 import FatalClientError, OAuth2Error
from oauthlib.openid.connect.core.endpoints.pre_configured import Server as WebApplicationServer

import frappe
from frappe.integrations.doctype.oauth_provider_settings.oauth_provider_settings import (
	get_oauth_settings,
)
from frappe.oauth import (
	OAuthWebRequestValidator,
	generate_json_error_response,
	get_server_url,
	get_userinfo,
)


def get_oauth_server():
	if not getattr(frappe.local, 'oauth_server', None):
		oauth_validator = OAuthWebRequestValidator()
		frappe.local.oauth_server  = WebApplicationServer(oauth_validator)

	return frappe.local.oauth_server

def get_urlparams_from_kwargs(param_kwargs):
	arguments = param_kwargs
	if arguments.get("data"):
		arguments.pop("data")
	if arguments.get("cmd"):
		arguments.pop("cmd")

	return urlencode(arguments)

@frappe.whitelist()
def approve(*args, **kwargs):
	r = frappe.request
	uri = url_fix(r.url.replace("+"," "))
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	try:
		(scopes, frappe.flags.oauth_credentials,) = get_oauth_server().validate_authorization_request(
			r.url, r.method, r.get_data(), r.headers
		)

		headers, body, status = get_oauth_server().create_authorization_response(uri=frappe.flags.oauth_credentials['redirect_uri'], \
				body=body, headers=headers, scopes=scopes, credentials=frappe.flags.oauth_credentials)
		uri = headers.get('Location', None)

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = uri

	except FatalClientError as e:
		return e
	except OAuth2Error as e:
		return e

@frappe.whitelist(allow_guest=True)
def authorize(*args, **kwargs):
	#Fetch provider URL from settings
	oauth_settings = get_oauth_settings()
	params = get_urlparams_from_kwargs(kwargs)
	request_url = urlparse(frappe.request.url)
	success_url = request_url.scheme + "://" + request_url.netloc + "/api/method/frappe.integrations.oauth2.approve?" + params
	failure_url = frappe.form_dict["redirect_uri"] + "?error=access_denied"

	if frappe.session['user']=='Guest':
		#Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?redirect-to=/api/method/frappe.integrations.oauth2.authorize?" + quote(params.replace("+"," "))

	elif frappe.session['user']!='Guest':
		try:
			r = frappe.request
			(scopes, frappe.flags.oauth_credentials,) = get_oauth_server().validate_authorization_request(
				r.url, r.method, r.get_data(), r.headers
			)

			skip_auth = frappe.db.get_value(
				"OAuth Client",
				frappe.flags.oauth_credentials["client_id"],
				"skip_authorization",
			)
			unrevoked_tokens = frappe.get_all("OAuth Bearer Token", filters={"status": "Active"})

			if skip_auth or (get_oauth_settings().skip_authorization == "Auto" and unrevoked_tokens):
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = success_url
			else:
				# Show Allow/Deny screen.
				response_html_params = frappe._dict(
					{
						"client_id": frappe.db.get_value("OAuth Client", kwargs["client_id"], "app_name"),
						"success_url": success_url,
						"failure_url": failure_url,
						"details": scopes,
					}
				)
				resp_html = frappe.render_template(
					"templates/includes/oauth_confirmation.html", response_html_params
				)
				frappe.respond_as_web_page("Confirm Access", resp_html)

		except FatalClientError as e:
			return e
		except OAuth2Error as e:
			return e

@frappe.whitelist(allow_guest=True)
def get_token(*args, **kwargs):
	r = frappe.request

	uri = url_fix(r.url)
	http_method = r.method
	body = r.form
	headers = r.headers

	#Check whether frappe server URL is set
	frappe_server_url = frappe.db.get_value("Social Login Key", "frappe", "base_url") or None
	if not frappe_server_url:
		frappe.throw(_("Please set Base URL in Social Login Key for Frappe"))

	try:
		headers, body, status = get_oauth_server().create_token_response(uri, http_method, body, headers, frappe.flags.oauth_credentials)
		out = frappe._dict(json.loads(body))
		if not out.error and "openid" in out.scope:
			token_user = frappe.db.get_value("OAuth Bearer Token", out.access_token, "user")
			token_client = frappe.db.get_value("OAuth Bearer Token", out.access_token, "client")
			client_secret = frappe.db.get_value("OAuth Client", token_client, "client_secret")
			if token_user in ["Guest", "Administrator"]:
				frappe.throw(_("Logged in as Guest or Administrator"))
			import hashlib
			id_token_header = {
				"typ":"jwt",
				"alg":"HS256"
			}
			id_token = {
				"aud": token_client,
				"exp": int((frappe.db.get_value("OAuth Bearer Token", out.access_token, "expiration_time") - frappe.utils.datetime.datetime(1970, 1, 1)).total_seconds()),
				"sub": frappe.db.get_value("User Social Login", {"parent":token_user, "provider": "frappe"}, "userid"),
				"iss": frappe_server_url,
				"at_hash": frappe.oauth.calculate_at_hash(out.access_token, hashlib.sha256)
			}
			import jwt
			id_token_encoded = jwt.encode(id_token, client_secret, algorithm='HS256', headers=id_token_header)
			out.update({"id_token": frappe.safe_decode(id_token_encoded)})
		frappe.local.response = out

	except FatalClientError as e:
		return e


@frappe.whitelist(allow_guest=True)
def revoke_token(*args, **kwargs):
	r = frappe.request
	uri = url_fix(r.url)
	http_method = r.method
	body = r.form
	headers = r.headers

	headers, body, status = get_oauth_server().create_revocation_response(uri, headers=headers, body=body, http_method=http_method)

	frappe.local.response['http_status_code'] = status
	if status == 200:
		return "success"
	else:
		return "bad request"

@frappe.whitelist()
def openid_profile(*args, **kwargs):
	picture = None
	first_name, last_name, avatar, name = frappe.db.get_value("User", frappe.session.user, ["first_name", "last_name", "user_image", "name"])
	frappe_userid = frappe.db.get_value("User Social Login", {"parent":frappe.session.user, "provider": "frappe"}, "userid")
	request_url = urlparse(frappe.request.url)
	base_url = frappe.db.get_value("Social Login Key", "frappe", "base_url") or None

	if avatar:
		if validate_url(avatar):
			picture = avatar
		elif base_url:
			picture = base_url + '/' + avatar
		else:
			picture = request_url.scheme + "://" + request_url.netloc + avatar

	user_profile = frappe._dict({
			"sub": frappe_userid,
			"name": " ".join(filter(None, [first_name, last_name])),
			"given_name": first_name,
			"family_name": last_name,
			"email": name,
			"picture": picture
		})

	frappe.local.response = user_profile

def validate_url(url_string):
	try:
		r = frappe.request
		headers, body, status = get_oauth_server().create_userinfo_response(
			r.url,
			headers=r.headers,
			body=r.form,
		)
		body = frappe._dict(json.loads(body))
		frappe.local.response = body
		return

	except (FatalClientError, OAuth2Error) as e:
		return generate_json_error_response(e)


@frappe.whitelist(allow_guest=True)
def openid_configuration():
	frappe_server_url = get_server_url()
	frappe.local.response = frappe._dict(
		{
			"issuer": frappe_server_url,
			"authorization_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.authorize",
			"token_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.get_token",
			"userinfo_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.openid_profile",
			"revocation_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.revoke_token",
			"introspection_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.introspect_token",
			"response_types_supported": [
				"code",
				"token",
				"code id_token",
				"code token id_token",
				"id_token",
				"id_token token",
			],
			"subject_types_supported": ["public"],
			"id_token_signing_alg_values_supported": ["HS256"],
		}
	)


@frappe.whitelist(allow_guest=True)
def introspect_token(token=None, token_type_hint=None):
	if token_type_hint not in ["access_token", "refresh_token"]:
		token_type_hint = "access_token"
	try:
		bearer_token = None
		if token_type_hint == "access_token":
			bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})
		elif token_type_hint == "refresh_token":
			bearer_token = frappe.get_doc("OAuth Bearer Token", {"refresh_token": token})

		client = frappe.get_doc("OAuth Client", bearer_token.client)

		token_response = frappe._dict(
			{
				"client_id": client.client_id,
				"trusted_client": client.skip_authorization,
				"active": bearer_token.status == "Active",
				"exp": round(bearer_token.expiration_time.timestamp()),
				"scope": bearer_token.scopes,
			}
		)

		if "openid" in bearer_token.scopes:
			sub = frappe.get_value(
				"User Social Login",
				{"provider": "frappe", "parent": bearer_token.user},
				"userid",
			)

			if sub:
				token_response.update({"sub": sub})
				user = frappe.get_doc("User", bearer_token.user)
				userinfo = get_userinfo(user)
				token_response.update(userinfo)

		frappe.local.response = token_response

	except Exception:
		frappe.local.response = frappe._dict({"active": False})
