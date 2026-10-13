> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# 01 — Debug : quatre pannes, quatre preuves

## Objectif
Distinguer image, processus, scheduler et filtrage réseau, puis corriger la **cause**, pas seulement redémarrer le pod. Durée cible : 3–6 min; borne de sécurité <10 min.

## Étapes
1. `bash docs/exercices/01-debug/run.sh` : préflight, namespace `ex-debug` PSS restricted.
2. Tag volontairement inexistant sur `docker.io/library/busybox` : attendre **ImagePullBackOff**, lire get/describe/logs/events, corriger par le digest BusyBox valide.
3. Commande `exit 1` : observer **CrashLoopBackOff**, exit code 1 et logs précédents; recréer avec un processus stable.
4. Requests **1000 CPU / 1Ti** : comparer l'allocatable des nœuds; observer **Pending**, PodScheduled=False/Unschedulable; réduire à 10m/16Mi et limits 100m/64Mi.
5. Serveur/client HTTP : prouver une connexion initiale, appliquer deny ingress, constater l'échec sur IP de pod (pas de confusion DNS), autoriser seulement client → serveur TCP/8080, vérifier `netpol-ok`.
6. Nettoyage automatique; secours : `bash docs/exercices/01-debug/cleanup.sh`.

## Résultat attendu
Quatre lignes PASS, chaque correction suivie de Ready ou de HTTP fonctionnel, puis namespace absent. Un timeout n'est **pas** une validation. Une NetworkPolicy rejetée par admission n'est **pas** un trafic bloqué.

## Commandes de diagnostic
Pendant une étape (ou en rejouant un manifeste manuellement dans le namespace possédé) :
```bash
kubectl -n ex-debug get pods -o wide
kubectl -n ex-debug describe pod image
kubectl -n ex-debug logs crash --previous
kubectl -n ex-debug get events --sort-by=.lastTimestamp
kubectl get nodes -o custom-columns=NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory
kubectl -n ex-debug describe networkpolicy server-ingress
kubectl -n ex-debug get endpointslice
```
**Piège observé dans ce lab** : un polling de 2 s a raté `CrashLoopBackOff` et voyait seulement `Error`. Le script corrigé capture le **watch API**, qui montre réellement `waiting.reason=CrashLoopBackOff`; le describe ultérieur peut déjà être revenu à Terminated/Error. Ce n'est pas une raison pour inventer un statut. Les logs `--previous` ont parfois été supprimés par le runtime; le script conserve aussi les logs courants, le code de sortie et les événements.

Les logs peuvent ne pas exister pour ImagePull/Pending. Le refus NetworkPolicy n'apparaît généralement pas comme un événement Kubernetes : pods Ready + endpoint présent + essai contrôlé avant/après établissent la preuve.

## Ce que ça prouve — trois lignes
- Je distingue un échec de téléchargement d'un processus qui plante grâce aux états et aux logs précédents.
- Je sais relier Pending aux requests et à l'allocatable, sans saturer réellement une machine.
- Je démontre un filtrage réseau par un test avant/après, sans confondre disponibilité des pods et connectivité.
