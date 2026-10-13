> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# 03 — Ressources : QoS et OOM limité

## Objectif
Relier requests/limits au scheduling et à la classe QoS, puis distinguer OOM **de conteneur** et OOM **de nœud**. Durée cible : 1–3 min; borne de sécurité <10 min.

## Étapes
1. `bash docs/exercices/03-resources/run.sh` : préflight; namespace `ex-resources` restricted, sans LimitRange pour ne pas injecter des defaults dans BestEffort.
2. Guaranteed : requests=limits CPU **50m**, mémoire **32Mi**. Burstable : request **10m/16Mi**, limit **100m/64Mi**. BestEffort : ni requests ni limits, un simple `sleep` de faible RSS.
3. Lire **`.status.qosClass`**, pas seulement déduire la classe du manifeste.
4. Un seul conteneur, limit **64Mi**, construit jusqu'à 160 blocs d'environ 1Mi : le cgroup le tue avant l'allocation complète. RestartPolicy=Never conserve **OOMKilled / exitCode=137**.
5. Corriger en retirant le memory hog sans relever arbitrairement la limite; constater Completed/exitCode=0.
6. Lire sur s1 **uniquement** les lignes system-reserved/kube-reserved/eviction-* depuis `/etc/rancher/k3s/config.yaml`. Ne jamais afficher le fichier complet (token possible).
7. Vérifier l'absence de réservations kubelet sur a1/a2 et l'état Ready final, **sans modifier les agents**. Nettoyage automatique ou `cleanup.sh`.

## Résultat attendu
Guaranteed/Burstable/BestEffort observés, OOMKilled et 137, correction Completed/0; réglages s1 réellement lus; gap agents constaté; cinq nœuds toujours Ready.

## D11 : lien avec l'incident réel
Voir DECISIONS.md, D11 (private historical material omitted).
- **D11** : charge cumulée, absence de réservation, OOM-kills du noyau visant k3s/etcd et latence fsync. Ce n'était pas ce petit exercice cgroup. Les serveurs ont reçu réservations et seuils d'éviction pour rendre de la mémoire avant l'OOM du nœud.
- **Exercice** : dépassement de la limite 64Mi d'un conteneur. La preuve porte sur son statut terminal; elle ne reproduit ni une pression globale de nœud ni la sélection de pods évincés.
- **Gap connu** : les agents n'ont **aucune réservation kubelet**. Aucun changement n'est réalisé ici. Les seuils/valeurs observés sont dans `evidence/exercices/03-s1-kubelet.txt`.
- `exitCode=137` seul n'identifie pas la cause (SIGKILL peut avoir d'autres origines); **reason=OOMKilled** complète la preuve. QoS n'est pas une immunité contre l'OOM; le kubelet utilise aussi requests, dépassement et priorité pour l'éviction.

## Commandes de diagnostic
```bash
kubectl -n ex-resources get pods -o custom-columns=NAME:.metadata.name,QOS:.status.qosClass
kubectl -n ex-resources describe pod oom
kubectl -n ex-resources get pod oom -o jsonpath='{.status.containerStatuses[0].state.terminated}'
kubectl -n ex-resources logs oom
kubectl -n ex-resources get events --sort-by=.lastTimestamp
kubectl get nodes
```

## Ce que ça prouve — trois lignes
- Je vérifie les classes QoS réellement attribuées et je distingue réservation scheduler de plafond cgroup.
- Je provoque et diagnostique un OOM de conteneur de 64Mi sans mettre le nœud sous pression artificielle.
- Je relie ce test limité à D11 honnêtement et j'identifie les réservations manquantes sur les agents.
