# Carte documentaire

[English overview](../README.md) · [Accueil français](../README.fr.md)

## Lire le projet

| Document | Question traitée |
|---|---|
| [README anglais](../README.md) | Quelle est la valeur du projet, et quelles preuves peut-on citer ? |
| [README français](../README.fr.md) | Où commencer selon mon objectif ? |
| [Architecture](architecture.md) | Où passent les données, les identités et les décisions ? |
| [Parcours](learning-path.md) | Comment apprendre sans confondre runner et raisonnement ? |
| [Démo](demo.md) | Que montrer en cinq minutes sans modifier le cluster ? |
| [Bilan de preuves](evidence-summary.md) | Quels résultats sont datés et quels brouillons ont été supersédés ? |
| [Limites](limitations.md) | Quels compromis et inconnues restent après les PASS ? |
| [Reproduction](reproducibility.md) | Quels prérequis manquent à une reconstruction depuis un clone vierge ? |

## Passer de la vue au code

| Fonction | Entrée |
|---|---|
| VM / cluster | [Libvirt](../infra/libvirt/README.md), [k3s](../infra/k3s/README.md) |
| Réseau / ingress / stockage | [Cilium](../platform/cilium/README.md), [Traefik](../platform/ingress/README.md), [stockage](../platform/storage/README.md) |
| Source et GitOps | [Forgejo](../platform/forgejo/README.md), [Argo CD](../platform/argocd/README.md), [seed](../platform/gitops-seed/README.md) |
| Confiance et identité | [Services](../infra-services/README.md), [PKI](../infra-services/pki/README.md), [identité](../infra-services/identity/README.md), [secrets](../infra-services/secrets/README.md) |
| Exploitation | [Observabilité](../infra-services/observability/README.md), [backup](../infra-services/backup/README.md), [registre](../infra-services/registry/README.md) |
| SOC | [Vue d'ensemble](../soc/README.md), [Kafka](../soc/kafka/README.md), [Vector](../soc/pipeline/README.md), [OpenSearch](../soc/opensearch/README.md), [détection](../soc/detection/README.md) |
| Capteurs / intelligence | [Zeek](../soc/zeek/README.md), [Falco](../soc/falco/README.md), [MISP](../soc/misp/README.md), [trafic](../soc/traffic/README.md) |
| Sécurité plateforme | [Hardening](../hardening/README.md), [Kyverno](../hardening/kyverno/README.md), [réseau](../hardening/netpol/README.md), [RBAC](../hardening/rbac/README.md), [PSS](../hardening/pss/README.md) |
| Application / delivery | [Application](../app/README.md), [DevSecOps](../devsecops/README.md) |
| Pratique / vérification | [Exercices](exercices/README.md), [scénarios](../scenarios/README.md), [tests](../tests/README.md), [audits](../audits/README.md) |

## Ce qui a changé par rapport aux documents d'origine

Les anciens README P8, guide opérateur, fiche imprimable et oral mêlaient accès privé, échéances personnelles et différents checkpoints de la journée. Ils ne sont pas les guides publics de ce package. Les nouvelles pages reprennent leurs enseignements, réconcilient les corrections ultérieures et remplacent les dessins liés à l'infrastructure privée par des schémas Mermaid.

Les rapports et logs bruts restent privés. Le [bilan](evidence-summary.md) fournit des références de provenance et empreintes de documents sélectionnés, sans liens vers des fichiers absents. Une empreinte identifie un document examiné ; elle n'en certifie ni le contenu ni une nouvelle exécution.

Les README de composants décrivent leurs propres prérequis et effets. Le parcours général ne les autorise pas implicitement. En cas de contradiction, séparer date de l'observation, contrat du code conservé et vérification nouvelle à produire, plutôt que choisir la phrase la plus favorable.
