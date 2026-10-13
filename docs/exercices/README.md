> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Exercices Kubernetes — phase F

Petits exercices du **lab personnel**, pas une simulation de production. Depuis lab controller :

```bash
cd /data/k8s-lab
source infra/k3s/env.sh
bash docs/exercices/01-debug/run.sh
bash docs/exercices/02-lifecycle/run.sh
bash docs/exercices/03-resources/run.sh
bash docs/exercices/04-control-plane/run.sh
```

| Module | Namespace | Sujet | Preuve |
|---|---|---|---|
| [01 Debug](01-debug/FICHE.md) | `ex-debug` | 4 pannes → diagnostic → correction | `evidence/exercices/01.log` |
| [02 Lifecycle](02-lifecycle/FICHE.md) | `ex-lifecycle` | v1/v2/v3, rollback, PDB, cordon bref | `evidence/exercices/02.log` |
| [03 Ressources](03-resources/FICHE.md) | `ex-resources` | QoS, OOM cgroup, D11 | `evidence/exercices/03.log` |
| [04 Control plane](04-control-plane/FICHE.md) | `ex-control-plane` | membres etcd, readyz, snapshot | `evidence/exercices/04.log` |

## Contrat de sécurité / relecture

- Chaque script commence par `make -s status-quick`, puis vérifie **5 nœuds Ready** et **RAM hôte disponible ≥ 4 GiB**. Échec/UNKNOWN = arrêt avant toute mutation.
- Un verrou empêche deux exercices simultanés. Les sorties réelles sont **ajoutées** au journal, avec un timestamp et le code retour. Ne pas confondre les anciennes tentatives avec la dernière.
- Plafond automatique : 550 s, puis au maximum 20 s avant terminaison forcée (<10 min). C'est une borne d'exécution, pas une promesse de réussite si le cluster est lent.
- Namespaces exclusivement `ex-*`, label d'appartenance `lab.k8s/exercise=phase-f`, PSS **restricted**. Un namespace étranger n'est jamais adopté/supprimé. Fin/erreur/signal : suppression du namespace puis lecture de confirmation.
- Budget usuel : BusyBox épinglé `1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e`, request 10m/16Mi, limit 100m/64Mi. Aucun jeton SA, hostPath, privilège ou volume persistant.
- Exceptions pédagogiques explicites : requests impossibles (pod jamais planifié), BestEffort sans requests/limits (simple sleep), OOM limité à 64Mi. Pas de stress de nœud.
- Les politiques Kyverno ciblant demo/dev/staging/prod/scen-* ne justifient pas de modifier ces namespaces pour l'exercice. Les registres autorisés restent respectés. `apply --dry-run=server` révèle l'admission effective; aucune politique globale n'est modifiée.
- Seules exceptions au périmètre namespace : **drain dry-run uniquement** et cordon/uncordon **a2**; lecture de config kubelet filtrée **avant sortie**; save/ls/delete du **seul** snapshot `ex-snapshot` sur s1. Jamais de restauration, drain réel, reboot ou modification des VM/hôte.
- `cleanup.sh` peut être relancé. Pour Lifecycle, le trap remet a2 schedulable et une garde indépendante fait un uncordon à 20 s si le processus principal est interrompu. Une panne API totale peut empêcher cette remise en état : le script doit alors rester FAIL, pas promettre une garantie physique impossible.
- Ne lancer ni `tests/phase-p1.sh` ni `soc/detection/test-live.py`. Aucun commit effectué par les scripts.

## Résultats réellement vérifiés

Voir le résumé historique dans `docs/evidence-summary.md` (depuis la racine), sans journaux privés distribués. Les fiches décrivent les résultats **attendus**; seuls les journaux réels et ce rapport attestent les observations.

## Suite — après l'entretien et le gel


- HPA / KEDA : autoscaling sur CPU et métriques/événements, requests correctement dimensionnées.
- Chaos Mesh : fautes réseau/processus dans des namespaces jetables; pas sur les control-plane.
- k6 : charge HTTP plafonnée, latences et taux d'erreur avec un budget mémoire/CPU préalable.
- iperf3 / netem : débit, latence et perte contrôlés; préférer des pods isolés, aucune règle réseau hôte improvisée.
