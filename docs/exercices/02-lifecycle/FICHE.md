> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# 02 — Lifecycle : rollout, rollback et disruptions

## Objectif
Observer un déploiement qui reste disponible malgré une mauvaise version et distinguer PDB, drain et cordon. Durée cible : 3–5 min; borne de sécurité <10 min.

## Étapes
1. `bash docs/exercices/02-lifecycle/run.sh` : préflight; deux replicas v1 sur **lab-a2** dans `ex-lifecycle`.
2. RollingUpdate **maxUnavailable=0 / maxSurge=1** vers v2; vérifier la réponse HTTP.
3. v3 a une readiness `/unready` inexistante : le rollout atteint **ProgressDeadlineExceeded**, mais les deux pods v2 restent disponibles.
4. Une sonde cliente émet 75 requêtes, une par seconde; le journal `02-http-probe.txt` doit contenir 75 OK v2, zéro échec. `kubectl rollout undo` restaure v2.
5. PDB **minAvailable=2**, donc **disruptionsAllowed=0**. `kubectl drain lab-a2 --dry-run=server` ne fait aucune éviction réelle et est limité par un selector à nos pods.
6. Dans la version observée ici, le dry-run serveur **interroge réellement le PDB**, affiche `Cannot evict pod as it would violate the pod's disruption budget`, puis finit en timeout attendu (15 s, code 1). Le script exige cette cause précise et ne traite pas une erreur générique comme une preuve. Preuve complémentaire : requête API Eviction avec `deleteOptions.dryRun=[All]` et `?dryRun=All`, attendue refusée par le PDB. Certaines versions de `kubectl drain` dry-run se limitent à afficher « would evict » : leur succès seul ne prouve pas la décision du PDB.
7. Cordon a2 pendant cinq secondes, puis uncordon et read-back; trap et garde indépendante d'uncordon à 20 s. **Jamais a1**, jamais de drain réel.
8. Namespace supprimé automatiquement; `cleanup.sh` ne décorderonne pas arbitrairement un nœud potentiellement géré par une autre session.

## Résultat attendu
v1 puis v2; v3 non Ready avec ≥2 replicas disponibles; rollback v2; 75/75 sondes HTTP OK; refus de l'éviction dry-run; a2 schedulable à la fin. La sonde prouve l'absence d'interruption **dans la fenêtre et à sa résolution**, pas un SLA absolu.

## Commandes de diagnostic
```bash
kubectl -n ex-lifecycle get deployment,rs,pods -o wide
kubectl -n ex-lifecycle describe deployment lifecycle
kubectl -n ex-lifecycle rollout status deployment/lifecycle --timeout=45s
kubectl -n ex-lifecycle rollout history deployment/lifecycle
kubectl -n ex-lifecycle get pdb lifecycle -o yaml
kubectl get node lab-a2 -o jsonpath='{.spec.unschedulable}'
```
PDB protège les disruptions volontaires via Eviction; ni les pannes physiques, ni une suppression directe de pod ne deviennent impossibles. Cordon empêche les **nouvelles** planifications, il ne déplace pas les pods existants.

## Ce que ça prouve — trois lignes
- Je contrôle le compromis disponibilité/capacité du rolling update et je sais revenir à une révision saine.
- Je distingue un rollout bloqué d'une indisponibilité du service, avec des requêtes réellement mesurées.
- Je démontre le PDB sans éviction réelle et je remets le seul nœud autorisé schedulable.

## Références
Documentation Kubernetes : [Disruptions](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/) et [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/).
