"""Comprehensive fixtures and deterministic firmographics generator for AgentSphere AI mocks."""

from typing import Any

# Catalog of 60+ realistic companies across 6 major enterprise industries
COMPANY_CATALOG: list[tuple[str, str, str, str, int, str, int]] = [
    # B2B SaaS / Workflow / Ops (15)
    ("Synthetix AI", "synthetix.io", "B2B SaaS", "San Francisco, California, United States", 140, "Series B", 28_000_000),
    ("CloudScale Systems", "cloudscale.io", "B2B SaaS", "Seattle, Washington, United States", 320, "Series C", 65_000_000),
    ("DataPulse Technologies", "datapulse.io", "B2B SaaS", "Austin, Texas, United States", 85, "Series A", 16_000_000),
    ("OmniFlow Software", "omniflow.io", "B2B SaaS", "Boston, Massachusetts, United States", 210, "Series B", 35_000_000),
    ("ActionBridge Cloud", "actionbridge.com", "B2B SaaS", "Denver, Colorado, United States", 65, "Series A", 12_000_000),
    ("PipeStream Software", "pipestream.io", "B2B SaaS", "New York, New York, United States", 175, "Series B", 30_000_000),
    ("LogikSync Platform", "logiksync.com", "B2B SaaS", "Chicago, Illinois, United States", 115, "Series A", 18_000_000),
    ("AppForge Solutions", "appforge.tech", "B2B SaaS", "San Francisco, California, United States", 45, "Seed", 4_500_000),
    ("WorkVelocity AI", "workvelocity.com", "B2B SaaS", "Atlanta, Georgia, United States", 95, "Series A", 15_000_000),
    ("InsightGrid Technologies", "insightgrid.io", "B2B SaaS", "New York, New York, United States", 280, "Series C", 55_000_000),
    ("OpsMatrix Cloud", "opsmatrix.io", "B2B SaaS", "Austin, Texas, United States", 160, "Series B", 26_000_000),
    ("FlowMetric Systems", "flowmetric.com", "B2B SaaS", "Seattle, Washington, United States", 70, "Series A", 11_000_000),
    ("TaskWeave AI", "taskweave.io", "B2B SaaS", "San Francisco, California, United States", 50, "Seed", 5_000_000),
    ("CollabSphere Enterprise", "collabsphere.tech", "B2B SaaS", "Boston, Massachusetts, United States", 190, "Series B", 32_000_000),
    ("AutoCadence Software", "autocadence.com", "B2B SaaS", "Denver, Colorado, United States", 130, "Series B", 22_000_000),

    # Cloud Infrastructure & CyberSecurity (12)
    ("InfraGuard Security", "infraguard.io", "CyberSecurity", "San Francisco, California, United States", 180, "Series B", 34_000_000),
    ("KubeMesh Networks", "kubemesh.dev", "Cloud Infrastructure", "Seattle, Washington, United States", 90, "Series A", 14_000_000),
    ("SentryStack Ops", "sentrystack.com", "Cloud Infrastructure", "Austin, Texas, United States", 250, "Series C", 48_000_000),
    ("ZeroTrust Systems", "zerotrust.io", "CyberSecurity", "New York, New York, United States", 380, "Series C", 75_000_000),
    ("DevCipher Labs", "devcipher.tech", "CyberSecurity", "Boston, Massachusetts, United States", 60, "Series A", 10_000_000),
    ("PacketWave AI", "packetwave.io", "Cloud Infrastructure", "San Francisco, California, United States", 110, "Series B", 20_000_000),
    ("MeshShield Security", "meshshield.io", "CyberSecurity", "Denver, Colorado, United States", 140, "Series B", 25_000_000),
    ("CloudVortex Infrastructure", "cloudvortex.tech", "Cloud Infrastructure", "Chicago, Illinois, United States", 210, "Series B", 38_000_000),
    ("ApexDefense AI", "apexdefense.com", "CyberSecurity", "Austin, Texas, United States", 310, "Series C", 60_000_000),
    ("ByteFortress Security", "bytefortress.io", "CyberSecurity", "San Francisco, California, United States", 75, "Series A", 13_000_000),
    ("ScaleFabric Cloud", "scalefabric.net", "Cloud Infrastructure", "Seattle, Washington, United States", 160, "Series B", 27_000_000),
    ("CipherGateway Labs", "ciphergateway.com", "CyberSecurity", "New York, New York, United States", 85, "Series A", 15_000_000),

    # FinTech & Billing (10)
    ("PayFlow Systems", "payflow.io", "Fintech", "New York, New York, United States", 220, "Series B", 42_000_000),
    ("Moneta Cloud", "monetacloud.com", "Fintech", "San Francisco, California, United States", 340, "Series C", 70_000_000),
    ("LedgerScale Technologies", "ledgerscale.com", "Fintech", "Chicago, Illinois, United States", 130, "Series B", 24_000_000),
    ("ClearSettle Global", "clearsettle.io", "Fintech", "London, United Kingdom", 190, "Series B", 35_000_000),
    ("QuantInvoice Labs", "quantinvoice.com", "Fintech", "Boston, Massachusetts, United States", 80, "Series A", 14_000_000),
    ("RevenueStack AI", "revenuestack.io", "Fintech", "Austin, Texas, United States", 150, "Series B", 28_000_000),
    ("TreasuryPilot Cloud", "treasurypilot.com", "Fintech", "New York, New York, United States", 95, "Series A", 17_000_000),
    ("ApexBilling Systems", "apexbilling.io", "Fintech", "San Francisco, California, United States", 260, "Series C", 52_000_000),
    ("CreditMatrix Global", "creditmatrix.tech", "Fintech", "Charlotte, North Carolina, United States", 400, "Series C", 80_000_000),
    ("YieldForge AI", "yieldforge.com", "Fintech", "Miami, Florida, United States", 65, "Seed", 6_000_000),

    # HealthTech & Digital Health (10)
    ("OmniHealth Data", "omnihealth.io", "HealthTech", "Boston, Massachusetts, United States", 160, "Series B", 30_000_000),
    ("BioPulse Labs", "biopulse.com", "HealthTech", "San Diego, California, United States", 240, "Series C", 45_000_000),
    ("CareFlow Analytics", "careflow.io", "HealthTech", "Nashville, Tennessee, United States", 120, "Series B", 22_000_000),
    ("MedVance Systems", "medvance.io", "HealthTech", "San Francisco, California, United States", 350, "Series C", 75_000_000),
    ("ClinicalSync AI", "clinicalsync.com", "HealthTech", "New York, New York, United States", 90, "Series A", 16_000_000),
    ("AcuityBio Technologies", "acuitybio.tech", "HealthTech", "Boston, Massachusetts, United States", 70, "Series A", 12_000_000),
    ("VitalGraph Health", "vitalgraph.io", "HealthTech", "Chicago, Illinois, United States", 180, "Series B", 32_000_000),
    ("PharmLogic Cloud", "pharmlogic.com", "HealthTech", "Philadelphia, Pennsylvania, United States", 290, "Series C", 58_000_000),
    ("CareMetric Labs", "caremetric.io", "HealthTech", "Austin, Texas, United States", 105, "Series A", 18_000_000),
    ("PathogenDx AI", "pathogendx.tech", "HealthTech", "Seattle, Washington, United States", 55, "Seed", 5_500_000),

    # Staffing / HRTech / Recruiting (8)
    ("TalentBridge AI", "talentbridge.io", "Staffing", "New York, New York, United States", 140, "Series B", 25_000_000),
    ("Apex Workforce Solutions", "apexworkforce.com", "Staffing", "Chicago, Illinois, United States", 420, "Series C", 65_000_000),
    ("Nexus Staffing Systems", "nexusstaffing.com", "Staffing", "Dallas, Texas, United States", 210, "Series B", 36_000_000),
    ("PeopleHive Recruiting", "peoplehive.io", "Staffing", "San Francisco, California, United States", 85, "Series A", 14_000_000),
    ("HiringSphere Global", "hiringsphere.com", "Staffing", "Atlanta, Georgia, United States", 175, "Series B", 28_000_000),
    ("CrewMetric Cloud", "crewmetric.io", "Staffing", "Denver, Colorado, United States", 95, "Series A", 16_000_000),
    ("WorkstreamAI Solutions", "workstreamai.tech", "Staffing", "Austin, Texas, United States", 130, "Series B", 22_000_000),
    ("RecruitPulse Labs", "recruitpulse.com", "Staffing", "Boston, Massachusetts, United States", 60, "Seed", 6_000_000),

    # E-Commerce Tech & Supply Chain (8)
    ("CartVelocity AI", "cartvelocity.com", "E-Commerce", "Los Angeles, California, United States", 160, "Series B", 30_000_000),
    ("RouteOptim Logistics", "routeoptim.io", "Supply Chain", "Atlanta, Georgia, United States", 230, "Series B", 40_000_000),
    ("StoreFront Sync", "storefrontsync.com", "E-Commerce", "New York, New York, United States", 110, "Series A", 18_000_000),
    ("InventoryFlow AI", "inventoryflow.io", "Supply Chain", "Chicago, Illinois, United States", 310, "Series C", 55_000_000),
    ("ShipMatrix Cloud", "shipmatrix.tech", "Supply Chain", "Seattle, Washington, United States", 145, "Series B", 26_000_000),
    ("CheckoutPulse Labs", "checkoutpulse.com", "E-Commerce", "San Francisco, California, United States", 75, "Series A", 12_000_000),
    ("FulfillSync Global", "fulfillsync.io", "Supply Chain", "Dallas, Texas, United States", 280, "Series C", 48_000_000),
    ("RetailEdge AI", "retailedge.tech", "E-Commerce", "Austin, Texas, United States", 90, "Series A", 15_000_000),
]


def find_catalog_company(company_name_or_domain: str) -> tuple[str, str, str, str, int, str, int] | None:
    """Lookup company in catalog by name, domain or slug."""
    if not company_name_or_domain:
        return None
    raw = company_name_or_domain.lower().strip()
    slug = raw.replace(".io", "").replace(".com", "").replace(".tech", "").replace(".dev", "").replace(".net", "").replace(" ", "").replace("-", "")

    for entry in COMPANY_CATALOG:
        name, domain, industry, hq, headcount, stage, funding = entry
        c_slug = name.lower().replace(" ", "").replace("-", "")
        d_slug = domain.lower().split(".")[0].replace("-", "")
        if raw == name.lower() or raw == domain.lower() or slug == c_slug or slug == d_slug:
            return entry
    return None
