> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# 04 — Control plane : snapshot etcd sans restauration

## Objectif
Créer/lister/supprimer une sauvegarde à la demande, voir les membres etcd et la santé API, puis savoir expliquer une restauration **non exécutée**. Durée cible : 1–3 min; borne de sécurité <10 min.

## Étapes
1. `bash docs/exercices/04-control-plane/run.sh` : préflight, namespace témoin `ex-control-plane` (aucune charge applicative).
2. Lire les **vrais membres etcd** via `/db/info` sur **127.0.0.1:6443 de s1**. Ce handler K3s appelle MemberList; il autorise une connexion locale. Ne pas exposer l'endpoint sur l'hôte, ni copier certificat/clé/token.
3. Lire `/readyz?verbose` et vérifier **etcd ok**, **etcd-readiness ok**, **readyz check passed**.
4. Lister les snapshots avant l'opération. Refuser tout `ex-snapshot` non possédé. Enregistrer un marqueur local d'appartenance, puis `sudo k3s etcd-snapshot save --name ex-snapshot` sur s1.
5. `sudo k3s etcd-snapshot ls` : garder **nom exact** (le CLI ajoute le nœud et un timestamp), **taille >0** et **file:///var/lib/rancher/k3s/server/db/snapshots/...**.
6. `sudo k3s etcd-snapshot delete <nom-exact>` puis relister; le snapshot de l'exercice doit être absent et les anciens noms toujours présents. Nettoyage via trap/`cleanup.sh`.

## Résultat attendu
Trois membres votants avec peer URLs s1/s2/s3, readyz sain, snapshot enregistré avec taille/emplacement puis supprimé. **Non vérifié : restauration, intégrité applicative après restore, RPO/RTO et copie off-host.** Un fichier sauvegardé ne prouve pas qu'un restore fonctionne.

## Commandes de diagnostic
```bash
kubectl get nodes -l node-role.kubernetes.io/etcd -o wide
kubectl get --raw '/readyz?verbose'
scripts/ssh-node.sh lab-s1 'sudo k3s etcd-snapshot ls'
```
Les avertissements `Unknown flag ... in config.yaml, skipping` du sous-CLI snapshot n'exposent pas les valeurs et peuvent être bénins si l'opération et le read-back réussissent. Ne pas masquer un vrai code d'échec.

## Procédure de restauration — DOCUMENTATION SEULEMENT

**Ne pas exécuter dans ce lab pendant l'entretien/gel.** Requiert une autorisation de maintenance distincte, une copie intègre/off-host du snapshot, la version compatible et le **token serveur original** conservé séparément et jamais écrit dans un journal. Snapshot etcd ≠ sauvegarde des données des PVC.

1. Isoler le créneau de restauration; arrêter k3s sur **tous les serveurs** (les agents n'établissent pas le quorum etcd).
2. Sur **un seul serveur** choisi (s1), conserver le token via le mécanisme secret existant, puis lancer en maintenance :
   ```text
   k3s server --cluster-reset --cluster-reset-restore-path=<chemin-complet-du-snapshot>
   ```
   Ce n'est **pas** une commande du script. Si la config active S3 et la source est locale, ajouter `--etcd-s3=false`. Sans restore-path, cluster-reset réinitialise le membership sans restaurer un snapshot.
3. Quand K3s indique que le membership a été réinitialisé, relancer normalement le service k3s de s1 (**sans** garder cluster-reset dans sa configuration).
4. Sur s2/s3 toujours arrêtés, préserver à part leurs anciennes données puis retirer leur **seul** répertoire etcd/db K3s comme indiqué par la documentation de la version; relancer avec l'URL de s1 et le même token protégé afin qu'ils **rejoignent** le nouveau cluster, un à un. Ne pas démarrer les anciennes données etcd en parallèle comme si le quorum précédent existait encore.
5. Vérifier trois membres, readyz, Ready des nœuds, objets Kubernetes et les applications/PVC; reconnecter les agents selon la procédure K3s. Sur de nouveaux hôtes, traiter aussi les anciennes ressources Node et le token original obligatoire pour déchiffrer les données bootstrap.

Cette séquence est une explication de DR, **pas une répétition réalisée**.

## Ce que ça prouve — trois lignes
- Je vérifie les membres et la santé etcd avant une sauvegarde à la demande.
- Je conserve le nom exact, la taille et l'emplacement, puis je supprime uniquement mon snapshot et le vérifie.
- Je sais expliquer le reset sur un serveur et le rejoin des pairs, sans prétendre avoir testé la restauration.

## Références
[Documentation K3s etcd-snapshot](https://docs.k3s.io/cli/etcd-snapshot), [handler K3s /db/info](https://github.com/k3s-io/k3s/blob/master/pkg/etcd/etcd.go).
