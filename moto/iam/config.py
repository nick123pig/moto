import datetime
import json
import time

from boto3 import Session

from moto.core.exceptions import InvalidNextTokenException
from moto.core.models import ConfigQueryModel
from moto.iam import iam_backends

class RoleConfigQuery(ConfigQueryModel):
    def list_config_service_resources(
        self,
        resource_ids,
        resource_name,
        limit,
        next_token,
        backend_region=None,
        resource_region=None,
    ):
        # For aggregation -- did we get both a resource ID and a resource name?
        if resource_ids and resource_name:
            # If the values are different, then return an empty list:
            if resource_name not in resource_ids:
                return [], None

        role_list = self.aggregate_regions('roles',backend_region,resource_region)            
       
        if not role_list:
            return [], None

        # Pagination logic:
        sorted_roles = sorted(role_list)
        new_token = None

        # Get the start:
        if not next_token:
            start = 0
        else:
            # "Tokens" are region + \00 + resource ID.
            if next_token not in sorted_roles:
                raise InvalidNextTokenException()

            start = sorted_roles.index(next_token)

        # Get the list of items to collect:
        role_list = sorted_roles[start : (start + limit)]

        if len(sorted_roles) > (start + limit):
            new_token = sorted_roles[start + limit]

        return (
            [
                {
                    "type": "AWS::IAM::Role",
                    "id": role.split("\1e")[1],
                    "name": role.split("\1e")[1],
                    "region": role.split("\1e")[0],
                }
                for role in role_list
            ],
            new_token,
        )

    def get_config_resource(
        self, 
        resource_id, 
        resource_name=None, 
        backend_region=None, 
        resource_region=None
    ):

        role = self.backends["global"].roles.get(resource_id, {})

        if not role:
            return

        if resource_name and role.name != resource_name:
            return

        # Format the bucket to the AWS Config format:
        config_data = role.to_config_dict()

        # The 'configuration' field is also a JSON string:
        config_data["configuration"] = json.dumps(config_data["configuration"])

        # Supplementary config need all values converted to JSON strings if they are not strings already:
        for field, value in config_data["supplementaryConfiguration"].items():
            if not isinstance(value, str):
                config_data["supplementaryConfiguration"][field] = json.dumps(value)

        return config_data



role_config_query = RoleConfigQuery(iam_backends)
