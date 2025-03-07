# Grafana Dashboards for Apache Pulsar

This repository contains a collection of Grafana dashboards for monitoring Apache Pulsar that are specifically designed to be compatible with the [victoria-metrics-k8s-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/victoria-metrics-k8s-stack) used in the [Apache Pulsar Helmchart](https://github.com/apache/pulsar-helm-chart) since 4.0.0.

## Overview

Apache Pulsar is a distributed messaging and streaming platform. These dashboards provide visibility into Pulsar's performance metrics, health, and operational status when deployed in Kubernetes environments.

## Compatibility

These dashboards are explicitly designed to work with:

- [victoria-metrics-k8s-stack](https://github.com/VictoriaMetrics/helm-charts/blob/master/charts/victoria-metrics-k8s-stack) 
- [Apache Pulsar Helmchart 4.0.0+](https://github.com/apache/pulsar-helm-chart)

## Features

The dashboards in this repository provide monitoring for various Pulsar components:

- Brokers
- BookKeepers
- ZooKeepers / Oxia components
- Pulsar Proxies
- Functions Workers, Functions and Connectors (status: untested)

## Installation

### Prerequisites

- Kubernetes cluster with Pulsar
- victoria-metrics-k8s-stack installed in your cluster

### Importing the Dashboards

You can import the dashboard JSON files manually into Grafana or specify the download URLs in your values.yaml of your Apache Pulsar Helm chart deployment to get them pre-installed.
Please see the Apache Pulsar Helm chart's values yaml as an example in how this is achieved with victoria-metrics-k8s-stack.

## Contributing

Contributions to improve these dashboards are welcome. Please feel free to submit pull requests or open issues for any improvements or bug fixes.

## License

Apache License Version 2.0