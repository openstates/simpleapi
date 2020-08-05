import datetime
from openstates_metadata import lookup
from openstates.data.models import Person, Jurisdiction
from django.db.models import Q
from collections import defaultdict
from .framework import Resource, segment, Endpoint, Parameter


def parse_jurisdiction_param(jid):
    if len(jid) == 2:
        return lookup(abbr=jid).jurisdiction_id
    elif jid.startswith("ocd-jurisdiction"):
        return jid
    else:
        return lookup(name=jid).jurisdiction_id


def parse_chamber_param(chamber):
    return chamber


class PersonResource(Resource):
    def __init__(self, obj):
        self.obj = obj

    @segment
    def basic(self):
        return {
            "id": self.obj.id,
            "name": self.obj.name,
            "jurisdiction": self.obj.current_jurisdiction.name,
            "party": self.obj.primary_party or None,
            "current_role": self.obj.current_role,
        }

    @segment
    def extra_bio(self):
        return {
            "family_name": self.obj.family_name,
            "given_name": self.obj.given_name,
            "image": self.obj.image,
            "gender": self.obj.gender,
            "birth_date": self.obj.birth_date,
            "death_date": self.obj.death_date,
            "extras": self.obj.extras,
            "created_at": self.obj.created_at,
            "updated_at": self.obj.updated_at,
        }

    @segment
    def other_identifiers(self):
        return {
            "other_identifiers": [
                {"scheme": oi.scheme, "identifier": oi.identifier}
                for oi in self.obj.identifiers.all()
            ]
        }

    @segment
    def other_names(self):
        return {
            "other_names": [{"name": on.scheme} for on in self.obj.other_names.all()]
        }

    @segment
    def links(self):
        return {"links": [{"url": l.url, "note": l.note} for l in self.obj.links.all()]}

    @segment
    def sources(self):
        return {
            "sources": [{"url": l.url, "note": l.note} for l in self.obj.sources.all()]
        }

    @segment
    def offices(self):
        contact_details = []
        offices = defaultdict(dict)
        for cd in self.obj.contact_details.all():
            offices[cd.note][cd.type] = cd.value
        for office, details in offices.items():
            contact_details.append(
                {
                    "name": office,
                    "fax": None,
                    "voice": None,
                    "email": None,
                    "address": None,
                    **details,
                }
            )
        return {"offices": contact_details}


class JurisdictionResource(Resource):
    def __init__(self, obj):
        self.obj = obj

    @segment
    def basic(self):
        return {
            "id": self.obj.id,
            "name": self.obj.name,
            "url": self.obj.url,
            "classification": self.obj.classification,
        }


class JurisdictionEndpoint(Endpoint):
    parameters = [Parameter("classification", default=None)]
    wrap_resource = JurisdictionResource
    default_per_page = 52
    max_per_page = 100

    def get_results(self, classification, segments):
        jset = Jurisdiction.objects.all().order_by("name")
        if classification:
            jset = jset.filter(classification=classification)
        return jset


class PeopleEndpoint(Endpoint):
    parameters = [
        Parameter("jurisdiction"),
        Parameter("chamber", default=None),
        Parameter("name", default=None),
    ]
    wrap_resource = PersonResource

    def get_results(self, jurisdiction, chamber, name, segments):
        today = datetime.datetime.today().strftime("%Y-%m-%d")
        jurisdiction = parse_jurisdiction_param(jurisdiction)
        people = Person.objects.filter(
            Q(memberships__organization__jurisdiction__id=jurisdiction)
            & (Q(memberships__end_date__gt=today) | Q(memberships__end_date=""))
        ).distinct().order_by("name")

        if name:
            people = people.filter(name__icontains=name)

        if "contact_details" in segments:
            people.prefetch_related("contact_details")

        return people
