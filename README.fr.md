# K8S-LAB — apprendre Kubernetes par ses contrôles et ses preuves

[English overview](README.md) · [Parcours guidé](docs/learning-path.md) · [Architecture](docs/architecture.md) · [Carte documentaire](docs/documentation-map.md)

Ce lab relie exploitation Kubernetes, télémétrie de sécurité et livraison d'images signées. Il sert à comprendre ce qu'un contrôle fait réellement, comment le vérifier, et ce qu'il ne garantit pas. **Il ne représente pas une expérience de production.** La reconstruction de l'environnement depuis un clone vierge n'a pas été reproduite.

## Choisir sa lecture

| Votre objectif | Premier document | Ensuite |
|---|---|---|
| Comprendre le projet en quelques minutes | [README anglais](README.md) | [Démo de cinq minutes](docs/demo.md) |
| Comprendre les composants et leurs frontières | [Architecture](docs/architecture.md) | [Limites](docs/limitations.md) |
| Apprendre en manipulant progressivement | [Parcours](docs/learning-path.md) | [Exercices](docs/exercices/README.md) |
| Vérifier les affirmations du dossier | [Bilan daté](docs/evidence-summary.md) | [Périmètre de reproduction](docs/reproducibility.md) |
| Examiner le code sans cluster | [Application](app/README.md) | [Delivery](devsecops/README.md), [SOC](soc/README.md), [durcissement](hardening/README.md) |

## Ce que vous allez relier

- Trois serveurs k3s/etcd et deux agents, Cilium/Hubble, Traefik et stockage.
- Identité applicative Keycloak/LDAP, PKI de lab, OpenBao/ESO, métriques et sauvegarde.
- Zeek, audit Kubernetes et Falco, transport Kafka/Vector, recherche et alertes OpenSearch.
- Forgejo, CI Woodpecker, scan Trivy, registre zot, signatures cosign et déploiement Argo CD.
- Diagnostic de Pods, rollout/rollback, budgets mémoire, quorum et snapshots etcd.

Le principe de lecture est toujours le même : **configuration → observation → interprétation → limite**. Un Pod Ready ne prouve pas que ses événements arrivent au moteur de recherche. Une application Synced n'est pas forcément Healthy. Une sauvegarde présente n'est pas une restauration réussie.

## Commencer sans toucher à l'infrastructure

Depuis la racine du dépôt, avec Python 3 :

```sh
(cd app && python3 -m unittest discover -s tests -v)
```

Ce test porte uniquement sur la validation des commandes applicatives. Le [premier exercice de lecture](docs/learning-path.md) demande ensuite de suivre une règle réseau dans les manifests. Il n'exige ni kubeconfig ni installation.

Pour un cluster déjà provisionné et autorisé, la [démo](docs/demo.md) propose des consultations explicites. Les runners historiques donnaient automatiquement la solution et produisaient des preuves ; ils ne remplacent pas votre diagnostic manuel. **Ils sont désactivés dans la copie publique**, avec les scénarios SOC et leurs nettoyages, en attendant les corrections de sûreté détaillées dans [les blocages runtime](tools/RUNTIME_DISABLED.md). L'exercice Lifecycle peut cordonner brièvement un agent ; le module control-plane crée puis supprime un snapshot, sans restaurer etcd.

## Résultats datés, pas voyants permanents

Les rapports du **13 octobre 2026** documentent cinq scénarios défensifs et quatre exercices réussis. Un contrôle indépendant à **22:58:23 CEST** a obtenu **40/40 PASS** sur le smoke test en lecture seule, avec Kafka revenu à trois brokers prêts. Les anciens brouillons qui le donnaient encore dégradé ne décrivent donc plus ce relevé. Aucun scénario ni exercice complet n'a été rejoué pendant ce contrôle.

Le bilan conserve les incidents et compromis : perte de six indices SOC, cache disque unsafe, deux CRITICAL non corrigibles exclus du gate CI, IoC bruité sur une IP de nœud, révocation Intel à chaud défaillante et absence de PRA hors hôte. Voir le [bilan historique](docs/evidence-summary.md) et les [limites](docs/limitations.md).

Projet d'**Alexis Fructus**, présenté dans le dépôt `hades-x/k8s-security-lab`, copie de référence distincte du lab privé. Le propriétaire a choisi de ne pas ajouter de licence au projet pour le moment ; aucune licence MIT ou autre licence open source n'est revendiquée. Ne pas confondre publication effective et déploiement reproductible.
