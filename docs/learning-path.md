# Parcours d'apprentissage

[Accueil français](../README.fr.md) · [Architecture](architecture.md) · [Exercices](exercices/README.md)

Chaque étape demande une explication et une preuve. Lire une correction puis lancer un runner peut valider le script sans vous apprendre à diagnostiquer. Commencez par la lecture et l’observation. Les runners historiques sont conservés pour étude mais désactivés dans cette copie publique : voir [les blocages runtime](../tools/RUNTIME_DISABLED.md). Leur remise en service exige une adaptation et de nouveaux tests.

## Deux modes à ne pas mélanger

1. **Sans cluster** : lire le code, dessiner un flux, exécuter les tests purs et formuler une hypothèse. Aucune installation nécessaire.
2. **Sur un lab autorisé** : consulter des objets puis, dans une fenêtre distincte, jouer des exercices mutateurs. Un kubeconfig valide, des outils et une infrastructure saine sont des prérequis, pas des fichiers fournis par ce dépôt.

Les [résultats historiques](evidence-summary.md) ne sont pas vos propres observations. Notez pour chaque exercice : heure, contexte, commande, effet, sortie réelle, interprétation et nettoyage.

## Étape 1 — lire une frontière réseau sans cluster

Depuis la racine du dépôt :

```sh
python3 - <<'PY'
from pathlib import Path
for name in ('hardening/netpol/README.md',
             'hardening/netpol/isolate-template.yaml'):
    print('\n### ' + name)
    print(Path(name).read_text())
PY
```

Questions à résoudre avant de lire d'autres réponses :

- Quel label sélectionne la cible ? Quelle est la portée namespace ?
- Pourquoi une règle d'autorisation reste-t-elle additive ?
- Pourquoi la quarantaine inclut-elle DNS ?
- Pourquoi un administrateur peut-il encore faire `exec` ?

Livrable : un schéma source → destination, avec une règle permettant le flux et une règle de quarantaine le refusant. Il s'agit de configuration lue, **pas de paquets observés**.

## Étape 2 — distinguer santé du nœud et santé de l'application

Sur un cluster de lab déjà provisionné et explicitement autorisé, avec un kubeconfig choisi par l'opérateur :

```sh
kubectl config current-context
kubectl get nodes -o wide
kubectl get --raw '/readyz?verbose'
kubectl get pods -A
kubectl -n argocd get applications
```

Le contexte identifie la cible ; ne continuez pas s'il est inattendu. N'affichez jamais le kubeconfig brut. `Ready`, `Synced` et `Healthy` répondent à des questions différentes. Choisissez un Pod applicatif et reliez-le à son Deployment, sa Service et ses endpoints. N'utilisez pas `get secrets -o yaml` comme raccourci.

Livrable : trois observations datées, chacune avec une limite. Exemple de forme, pas sortie attendue : « état du nœud observé ; ne démontre pas la fraîcheur SOC ».

## Étape 3 — diagnostiquer avant de corriger

Lire [Debug](exercices/01-debug/FICHE.md). Pour chaque panne : écrire votre hypothèse, consulter status/events, proposer une correction minimale, puis relire la convergence. Les quatre sujets sont ImagePullBackOff, CrashLoopBackOff, Pending et NetworkPolicy.

Ne lancez pas d'emblée `run.sh` : il crée les fixtures, corrige les pannes et nettoie. Utilisez les manifests et la fiche dans leur périmètre `ex-debug` avec accord opérateur. Ne supprimez pas un namespace préexistant pour « repartir proprement ».

Livrable : symptôme → indice déterminant → correction → observation après correction. Un timeout réseau seul ne prouve pas une NetworkPolicy ; il faut les endpoints et, si disponible, le verdict Hubble correspondant.

## Étape 4 — rollout, rollback et disponibilité

Lire [Lifecycle](exercices/02-lifecycle/FICHE.md). Distinguer version désirée, ReplicaSets, disponibilité et réponse HTTP. Expliquer pourquoi une nouvelle version défaillante peut laisser l'ancienne servir, et ce qu'un PDB protège lors d'une éviction volontaire.

Le runner historique a joué un drain **dry-run**, puis un cordon/uncordon bref d'un agent. Le cordon est une mutation globale du nœud, même si les Pods restent en place. Panne API et interruption forcée peuvent empêcher le nettoyage ; pas de garantie automatique de retour à l'état initial. Aucun drain réel ni reboot n'appartient à cette première pratique.

Livrable : timeline rollout → panne → rollback, puis preuve que le nœud ciblé est schedulable.

## Étape 5 — mémoire, QoS et contention

Lire [Ressources](exercices/03-resources/FICHE.md), puis les [limites de capacité](limitations.md). Comparer requests, limits, QoS et consommation. Un OOM de conteneur sous une limite de 64 Mi n'est pas le même incident qu'un control-plane privé de mémoire et saturé en I/O.

Le rapport historique constate une réservation kubelet sur serveur et son absence sur les agents. Ne généralisez pas un flag d'installateur à tous les nœuds. Ne rejouez pas l'incident hôte pour illustrer la leçon.

Livrable : expliquer le risque d'overcommit sans confondre somme de limites et RAM réservée.

## Étape 6 — quorum, snapshot et restauration

Lire [Control plane](exercices/04-control-plane/FICHE.md). Relier trois votants, majorité, readiness API et catalogue de snapshots. Le runner historique a sauvegardé, listé puis supprimé un snapshot lors du test enregistré. Son nettoyage par préfixe ne garantit toutefois pas la propriété d’un snapshot créé concurremment ; le runner public est donc désactivé. Cela écrit sur un serveur et ne restaure pas etcd.

Livrable : un plan de restore indiquant sauvegarde hors hôte, identité des membres, token nécessaire, contrôle applicatif/PVC et décision de rollback. Ce plan reste non exécuté. Un petit restore Velero réussi ne prouve pas ce plan.

## Étape 7 — suivre un événement, puis tester une réponse

Lire la [chaîne SOC](architecture.md), puis [les scénarios défensifs](../scenarios/README.md). Choisir un cas DNS synthétique : indicateur → table Intel → événement → topic → document → moniteur → alerte. Relever la fenêtre temporelle et le contexte plutôt que le seul compteur de hits.

En pratique autorisée, séparer génération, détection, décision de réponse et vérification dataplane. Un label de quarantaine peut précéder sa prise en compte par Cilium. Une correspondance IoC n'est pas une compromission confirmée ; l'IP interne d'un nœud utilisée comme IoC a précisément montré ce piège dans ce lab.

Livrable : une timeline avec un résultat de détection, une preuve de confinement et ses limites. Ne ciblez ni la passerelle/hôte ni un réseau extérieur.

## Étape 8 — expliquer la supply chain

Lire [DevSecOps](../devsecops/README.md) et [l'application](../app/README.md). Exécuter les tests purs :

```sh
(cd app && python3 -m unittest discover -s tests -v)
```

Relier commit, digest construit, résultat du scan, signer attendu, valeurs GitOps et image effectivement exécutée. Dire explicitement ce que `--ignore-unfixed` exclut. Expliquer pourquoi SQL puis publication Kafka sans outbox n'assure pas une transaction métier exactement une fois.

Livrable final : présenter la [démo](demo.md) en cinq minutes, sans mutation, puis nommer une limite que les contrôles ne ferment pas. La première preuve à demander avant un nouveau déploiement est une reconstruction propre sur un environnement disposable, pas un nouveau badge.
