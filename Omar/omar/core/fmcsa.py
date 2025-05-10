import requests
import json
import time
import logging

# ──────────────────────────────  LOGGING  ────────────────────────────── #
logging.basicConfig(
    filename="fmcsa_app.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ──────────────────────────────  HELPERS  ────────────────────────────── #
def format_tax_ein(ein: str) -> str:
    if ein == "N/A" or not ein.isdigit() or len(ein) != 9:
        return ein
    return f"{ein[:2]}-{ein[2:]}"


def format_phone_number(phone: str) -> str:
    if phone == "N/A" or not phone.isdigit() or len(phone) != 10:
        return phone
    return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"


# ───────────────────────  FMCSA + DATASET QUERIES  ───────────────────── #
def get_company_details_from_fmcsa(identifier: str, identifier_type: str, webkey: str):
    base_url = "https://mobile.fmcsa.dot.gov/qc/services/"
    initial_endpoint = (
        f"carriers/docket-number/{identifier}/?webKey={webkey}"
        if identifier_type == "mc"
        else f"carriers/{identifier}?webKey={webkey}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://mobile.fmcsa.dot.gov/",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    company_details: dict[str, str] = {}

    try:
        time.sleep(1)
        response = requests.get(f"{base_url}{initial_endpoint}", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        content = data.get("content")
        if content is None:
            return {"error": f"No data found for {identifier_type.upper()} number {identifier}."}

        carrier = None
        if identifier_type == "dot":
            if isinstance(content, dict):
                carrier = content.get("carrier") if isinstance(content.get("carrier"), dict) else content
            elif isinstance(content, list) and content:
                first = content[0]
                carrier = first.get("carrier") if isinstance(first.get("carrier"), dict) else first
        else:
            if isinstance(content, list) and content:
                carrier = content[0].get("carrier", {})

        if not carrier:
            return {"error": f"Invalid structure for {identifier_type.upper()} number {identifier}."}

        dot_number = str(carrier.get("dotNumber", "N/A"))
        if dot_number == "N/A":
            return {"error": f"Unable to retrieve USDOT number for {identifier_type.upper()} number {identifier}."}

        # Try to pull docketNumber from top-level content
        if isinstance(content, list) and content:
            docket_number = str(content[0].get("docketNumber", "N/A"))
        else:
            docket_number = str(content.get("docketNumber", "N/A"))

        mc_number = docket_number if docket_number != "N/A" else str(carrier.get("mcNumber", "N/A"))

        company_details.update({
            "Legal Name": carrier.get("legalName", "N/A"),
            "DBA Name": carrier.get("dbaName") or "None",
            "Physical Address": (
                f"{carrier.get('phyStreet', '')} {carrier.get('phyCity', '')}, "
                f"{carrier.get('phyState', '')} {carrier.get('phyZipcode', '')}"
            ).strip() or "N/A",
            "Phone": format_phone_number(carrier.get("telephone", "N/A")),
            "USDOT Number": dot_number,
            "MC Number": mc_number,
            "Allow to Operate": (
                "Yes" if carrier.get("allowedToOperate") == "Y"
                else "No" if carrier.get("allowedToOperate") == "N"
                else carrier.get("allowedToOperate", "N/A")
            ),
            "Out of Service": carrier.get("outOfService", "N/A"),
            "Out of Service Date": carrier.get("oosDate") or "None",
            "Complaint Count": str(carrier.get("complaintCount", "N/A")),
            "Email": "Not Available",
            "Tax EIN": format_tax_ein(str(carrier.get("ein", "N/A"))),
            "Total Drivers": str(carrier.get("totalDrivers", "N/A")),
            "Total Power Units": str(carrier.get("totalPowerUnits", "N/A")),
            "Crash Total": str(carrier.get("crashTotal", "N/A")),
            "Fatal Crash": str(carrier.get("fatalCrash", "N/A")),
            "Injury Crash": str(carrier.get("injCrash", "N/A")),
            "Towaway Crash": str(carrier.get("towawayCrash", "N/A")),
            "Driver Inspections": str(carrier.get("driverInsp", "N/A")),
            "Driver OOS Inspections": str(carrier.get("driverOosInsp", "N/A")),
            "Driver OOS Rate": str(carrier.get("driverOosRate", "N/A")),
            "Driver OOS Rate National Average": str(carrier.get("driverOosRateNationalAverage", "N/A")),
            "Vehicle Inspections": str(carrier.get("vehicleInsp", "N/A")),
            "Vehicle OOS Inspections": str(carrier.get("vehicleOosInsp", "N/A")),
            "Vehicle OOS Rate": str(carrier.get("vehicleOosRate", "N/A")),
            "Vehicle OOS Rate National Average": str(carrier.get("vehicleOosRateNationalAverage", "N/A")),
            "Hazmat Inspections": str(carrier.get("hazmatInsp", "N/A")),
            "Insurance BIPD On File": str(carrier.get("bipdInsuranceOnFile", "N/A")),
            "Insurance BIPD Required": carrier.get("bipdInsuranceRequired", "N/A"),
            "Insurance BIPD Required Amount": str(carrier.get("bipdRequiredAmount", "N/A")),
            "Insurance Cargo On File": str(carrier.get("cargoInsuranceOnFile", "N/A")),
            "Insurance Cargo Required": carrier.get("cargoInsuranceRequired", "N/A"),
            "Broker Authority Status": carrier.get("brokerAuthorityStatus", "N/A"),
            "Common Authority Status": carrier.get("commonAuthorityStatus", "N/A"),
            "Contract Authority Status": carrier.get("contractAuthorityStatus", "N/A"),
            "Review Date": carrier.get("reviewDate") or "None",
            "Review Type": carrier.get("reviewType") or "None",
            "Safety Rating": carrier.get("safetyRating") or "None",
            "Safety Rating Date": carrier.get("safetyRatingDate") or "None",
            "Safety Review Date": carrier.get("safetyReviewDate") or "None",
            "Safety Review Type": carrier.get("safetyReviewType") or "None",
            "Status Code": carrier.get("statusCode", "N/A"),
            "Authority Status": "N/A",
            "Company Officer": "N/A",
        })

        # Authority endpoint (optional second request)
        time.sleep(1)
        authority_endpoint = f"carriers/{dot_number}/authority?webKey={webkey}"
        try:
            resp = requests.get(f"{base_url}{authority_endpoint}", headers=headers, timeout=10)
            resp.raise_for_status()
            auth_data = resp.json()
            a_content = auth_data.get("content", [])
            if a_content and isinstance(a_content, list):
                authority = a_content[0].get("authority", [])
                if authority and isinstance(authority, list):
                    company_details["Authority Status"] = authority[0].get("authStatus", "N/A")
        except requests.exceptions.RequestException as e:
            logging.error(f"Authority endpoint failed: {str(e)}")

        return {"details": company_details, "dot_number": dot_number}

    except Exception as e:
        logging.error(f"FMCSA API error: {str(e)}")
        return {"error": "API error occurred"}


# ───────────────────────  SAFER DATASET  ─────────────────────── #
def get_additional_details_from_dataset(dot_number: str):
    url = f"https://data.transportation.gov/resource/az4n-8mr2.json?dot_number={dot_number}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            return {
                "Phone": "N/A",
                "Email": "Not Available",
                "Company Officer": "N/A",
                "MC Number": "N/A"
            }
        rec = data[0]
        return {
            "Phone": format_phone_number(rec.get("phone", "N/A")),
            "Email": rec.get("email_address", "Not Available"),
            "Company Officer": rec.get("company_officer_1", "N/A"),
            "MC Number": rec.get("docket1", "N/A").replace("MC", "") if rec.get("docket1") else "N/A"
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"SAFER dataset request failed: {str(e)}")
        return {
            "Phone": "N/A",
            "Email": "Not Available",
            "Company Officer": "N/A",
            "MC Number": "N/A"
        }


# ───────────────────────  AGGREGATOR  ─────────────────────── #
def get_company_details(mc_number: str | None, dot_number: str | None, webkey: str):
    if mc_number and dot_number:
        return {"error": "Please enter either an MC number or a DOT number, not both."}
    if mc_number:
        identifier, identifier_type = mc_number, "mc"
    elif dot_number:
        identifier, identifier_type = dot_number, "dot"
    else:
        return {"error": "Please enter an MC number or a DOT number to search."}

    fmcsa_info = get_company_details_from_fmcsa(identifier, identifier_type, webkey)
    if "error" in fmcsa_info:
        return fmcsa_info

    details = fmcsa_info["details"]
    dot_number = fmcsa_info["dot_number"]

    dataset_info = get_additional_details_from_dataset(dot_number)
    details.update(dataset_info)

    # Prefer MC from dataset if FMCSA one is missing
    if details.get("MC Number", "N/A") == "N/A" and dataset_info.get("MC Number") != "N/A":
        details["MC Number"] = dataset_info.get("MC Number")

    normalized = {}
    for k, v in details.items():
        norm_key = (
            k.replace(" ", "_")
             .replace("(", "")
             .replace(")", "")
             .replace("-", "_")
             .replace(".", "")
             .replace("&", "and")
        )
        normalized[norm_key] = v

    return normalized
