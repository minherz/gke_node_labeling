"""
Copyright 2021 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
from http import HTTPStatus
import os
import requests
import sys

import google.auth
import googleapiclient.discovery


ZONE_LABEL = 'failure-domain.beta.kubernetes.io/zone'


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# [START get_node_data]
def get_node_data(node_name, node_label_names):
    try:
        with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as file:
            token = file.read()
    except OSError:
        eprint('Failed reading /var/run/secrets/kubernetes.io/serviceaccount/token')
        exit(1)
    except IOError:
        eprint('Failed to read token')
        exit(1)

    resp = requests.get(url='https://kubernetes.default.svc/api/v1/nodes/{node_name}'.format(
        node_name=node_name), headers={'Authorization': 'Bearer ' + token}, verify=False)
    if resp.status_code != HTTPStatus.OK:
        eprint('Failed to read data from ''{node}'' (status: {status})'.format(
            node=node_name, status=resp.status_code))
    info = resp.json()
    zone = 'us-central1-c'
    labels = {}
    for key, value in info['metadata']['labels'].items():
        if key == ZONE_LABEL:
            zone = value
        if key in node_label_names:
            labels[key] = value
    return labels, zone
# [END get_node_data]


# [START update_vm_labels]
def update_vm_labels(instance_name, zone, labels):
    creds, project_id = google.auth.default(
        scopes=['https://www.googleapis.com/auth/compute'])
    compute = googleapiclient.discovery.build(
        'compute', 'v1', credentials=creds)
    resp = compute.instances().get(project=project_id, zone=zone,
                                   instance=instance_name).execute()
    if 'error' in resp:
        eprint('Failed to get GCE instance info')
        exit(1)
    fingerprint = resp['labelFingerprint']
    # prevent overriding existing GKE labels
    for key, value in resp['labels'].items():
        labels[key] = value
    resp = compute.instances().setLabels(project=project_id, zone=zone, instance=instance_name, body={
        'labelFingerprint': fingerprint,
        'labels': labels}).execute()
    if 'error' in resp:
        eprint('Failed to set Cloud labels for ''{node}''\n').format(
            node=node_name)
        for err in resp['error']['errors']:
            eprint('code: {code} / location: {location} / msg: {msg}\n').format(
                code=err['code'], location=err['location'], msg=err['message'])
        exit(1)
# [END update_vm_labels]


# [START main]
def main(label_names):
    if not label_names:
        eprint('List of Kubernetes labels is empty.')
        exit(1)
    node_name = os.getenv('NODE_NAME')
    if node_name == '':
        eprint('Environment variable NODE_NAME is not defined')
        exit(1)

    node_labels, zone = get_node_data(node_name, label_names)
    update_vm_labels(node_name, zone, node_labels)
# [END main]


# [START run]
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '-n', '--name',
        nargs='+',
        help='Kubernetes label name to be set as Cloud label on GCE instance')

    args = parser.parse_args()

    main(args.name)
# [END run]
