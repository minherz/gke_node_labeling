# GKE Node Labeling

In Google Cloud a user can [break down you billing charges](https://cloud.google.com/billing/docs/how-to/bq-examples) by [labeling](https://cloud.google.com/compute/docs/labeling-resources) Cloud resources.
Unfortunately, it is not always possible to label particular resources.
For example, if a user wants to follow the spending of particular cluster node it cannot be done because GKE supports labeling on the [cluster level only](https://cloud.google.com/kubernetes-engine/docs/how-to/creating-managing-labels#about_labeling_clusters).

This solution runs on GKE clusters and labels GKE nodes based on their Kubernetes labels.

> **NOTE:** Kubernetes labels are not the same as Google Cloud labels

## How it works

The solution runs as a daemonset on a GKE cluster and sets the values of the configured Kubernetes labels on the GKE nodes to be Cloud labels of the GCE instances that run the nodes. Mind the [limits](https://cloud.google.com/resource-manager/docs/creating-managing-labels#requirements) of 64 labels per resource and the 63 characters. The solution does not do this level of validation.

The solution uses dedicated Kubernetes service account to get access to `nodes` resource. It assumes that GKE nodes run on GCE instances with an attached Cloud service account with scope 'https://www.googleapis.com/auth/compute' or the GKE cluster is configured with [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) and the dedicated Kubernetes service account is bound to Cloud service account with `instances.get` and `instances.setLabels` permissions.

## How to run it

The following instructions setup a demo cluster and deploy the solution. The instructions assume that Google Cloud SDK is [configured](https://cloud.google.com/sdk/docs/initializing) with a project id and the project has default network with a subnet in us-central1 region.

1. Create a GKE cluster with needed scope and 5 work nodes:

    ```bash
    # gcloud container clusters create test-cluster-1 -z us-central1-c --num-nodes=5 --scopes=compute-rw,default
    ```

1. Get the cluster credentials:

    ```bash
    > gcloud container clusters get-credentials test-cluster-1 -z us-central1-c
    ```

1. Assign a custom Kubernetes label to the GKE nodes:

    ```bash
    > i=0; for name in $(kubectl get nodes -o custom-columns=NAME:.metadata.name --no-headers); do kubectl label node $name workload="workload-$((i++))"; done
    ```

1. Deploy the solution

    ```bash
    > kubectl apply -f manifests/
    ```

    You will get an output like:

    ```bash
    serviceaccount/node-labeling-robot created
    clusterrole.rbac.authorization.k8s.io/node-info-reader created
    clusterrolebinding.rbac.authorization.k8s.io/node-labeling-robot-read-nodes created
    configmap/node-labeling-files created
    daemonset.apps/node-labeling created
    ```

Now you can check GCE instances to see they have Cloud labels same to Kubernetes labels from step 3 in addition to GKE label.

```bash
> for name in $(kubectl get nodes -o custom-columns=NAME:.metadata.name --no-headers); gcloud 
```

## What it does not do

* The solution does not pick up changes in labeling made to existing nodes _AFTER_ the deployment.
In order to implement it, the following changes should be applied:

  * Move `"node-labeling"` container from `initContainers` to `containers` and remove the pause container.
  * Implement [watching](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes) node resource for changes.

* The solution picks up Kubernetes labels only. It does not look for annotations, taints or other node specific metadata.

* The solution does not create a specialized namespace. Everything is deployed into the `default` namespace.
