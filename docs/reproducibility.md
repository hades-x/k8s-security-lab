# Reproduction : ce qui est conservé, ce qui reste à prouver

[Accueil](../README.md) · [Limites](limitations.md) · [Documentation](documentation-map.md)

**Aucun déploiement depuis un clone vierge n'a été reproduit pour cette publication.** Les résultats du 13 octobre 2026 viennent du lab d'origine. Un smoke réussi sur ce lab existant ne démontre pas qu'un autre opérateur peut le reconstruire depuis le package public.

## Niveaux de vérification

| Niveau | Ce que l'on peut exercer | Ce que cela ne démontre pas |
|---|---|---|
| Lecture locale | Documentation, manifests, valeurs, code | Compatibilité réelle des charts, admission ou disponibilité |
| Tests purs | Validation métier de l'application, tests offline explicitement inspectés | Exécution de ses dépendances SQL/Kafka/Valkey |
| Validation avec outils/caches | Syntaxe, rendu Helm, schémas et politiques | Pod démarré, transport réel ou restaurabilité |
| Consultation d'un lab existant | Objets Kubernetes et endpoints autorisés | Fresh-clone install, nouvelle CI ou nouveau scénario |
| Acceptation mutatrice | Installation, fixtures, traffic, promotion, restore ciblé | PRA complet, indépendance physique ou performance soutenue |

Les tests de phase ne sont pas une suite locale universelle. Certains scripts « static » téléchargent charts ou schémas si le cache manque. Offline signifie ici **sans réseau** uniquement lorsque toutes leurs dépendances sont disponibles et que le script a été inspecté pour le confirmer.

## Premier contrôle sans infrastructure

Python 3 et les fichiers de l'application suffisent :

```sh
(cd app && python3 -m unittest discover -s tests -v)
```

La commande couvre le domaine de validation des commandes. Dans ce package, `make check` (également `make ci` et `make test`) lance les checks offline et l'audit public ; `make test-offline` limite le passage aux suites locales. Ces cibles ne sont pas le `make test` live du lab d'origine. Ne pas transposer l'ancien contrat P8 de cibles `up/down/load/chaos` comme s'il avait été exercé.

`make smoke` est une consultation live distincte et opt-in. Les entrées runtime requièrent `LAB_ALLOW_RUNTIME=yes` et la revue des [prérequis opérateur](../tools/DEPENDENCIES.md). `make start`, `make stop` et `make creds` sont bloqués dans le package : l'orchestration de l'hôte privé n'est pas distribuée. L'opérateur doit gérer son propre lab disposable ; ces barrières ne prouvent pas une procédure de bootstrap complète.

Le package remplace les identités de nœuds par des noms synthétiques et l'interface uplink par un placeholder explicite. Les nouveaux disques de son provisioner utilisent `cache=none`, contrairement au compromis unsafe historique. Les tailles de provisioning et attentes de tests d'origine restent à réconcilier : les allocations observées dans le bilan ne sont pas une garantie que ce bootstrap produit le même environnement.

## Prérequis opérateur pour tenter une recréation

Avant toute commande mutatrice, préparer un environnement disposable dédié et un plan approuvé :

1. Virtualisation KVM/libvirt, permissions opérateur, ressources disponibles et stockage durable. Les pins/scripts de VM et binaires décrivent principalement des invités et outils x86_64 ; une machine ARM n'est pas un équivalent transparent.
2. Vérification de tous les chemins et interfaces hôte. De nombreux helpers supposent `/data/k8s-lab`, `.secrets/` et `bin/`. `/data/k8s-lab` est un chemin de déploiement de référence configurable par revue du code, pas la racine de tous les clones.
3. Réseau de lab sans collision, CIDR autorisés, sortie NAT adaptée et route cliente limitée. Aucun inventaire d'autres VM ou script de remise en route de l'infrastructure privée n'est fourni comme prérequis public.
4. Outils explicitement installés et versions/pins relus : Python, Bash, kubectl, Helm et outils propres aux composants. Les binaires et caches du lab d'origine ne sont pas inclus.
5. Nouvelles clés SSH du lab, kubeconfig et secrets générés localement avec permissions restrictives ; aucun fichier privé à importer depuis l'environnement d'origine.
6. Nouvelle PKI et nouveau signer cosign. Régénérer/interconnecter CA, bundles clients, issuer ACME, trust registry, policy d'admission et signatures des images. Ne pas reprendre les anciens trust roots ou promettre que leurs certificats restent valides.
7. Accès aux releases, charts, registries et paquets requis. Les pins permettent de contrôler les octets attendus ; ils n'assurent pas leur disponibilité ni un bootstrap air-gapped. Certains init/replay paths requièrent des dépôts de paquets.
8. Budget cumulé CPU/RAM/I/O, seuils d'arrêt, sauvegarde hors hôte et fenêtre d'essai. Ne pas reproduire la stratégie unsafe cache pour des données à conserver.

Lire chaque installateur et ses dépendances avant de choisir l'ordre de bootstrap. L'ordre logique est infrastructure/cluster → CNI/ingress/storage → GitOps et services de confiance → SOC → durcissement et delivery → exercices. Il reste à valider comme procédure complète du package, y compris les interdépendances PKI/registry/admission et les caches omis.

## Classes d'effets à anticiper

- `env.sh` peut créer des répertoires d'outils et redéfinir `HOME`, `PATH` et `KUBECONFIG` ; l'isoler dans un sous-shell ne provisionne rien.
- Installer/réconcilier change des objets Kubernetes et peut télécharger des dépendances ou générer des secrets.
- Mesurer le lag peut créer un client temporaire ; le nom `status` ne garantit pas une simple lecture.
- Tests SOC et scénarios créent du trafic/ressources et peuvent modifier temporairement la consommation ou le confinement.
- Exercices utilisent des namespaces possédés ; Lifecycle cordonne un agent et control-plane écrit un snapshot.
- Backup drills peuvent supprimer/recréer une fixture ; tests cluster peuvent rebooter un serveur. Réparation de disque ou allocation de primaire peut détruire des données.

Ne pas utiliser une restauration, un « reset » ou un cleanup général pour réparer un prérequis manquant. Ne jamais toucher aux workloads ou VM non créés pour cette tentative.

## Ce qui permettrait de revendiquer une reconstruction

Une future preuve doit partir d'un clone vierge, sans `.secrets`, état VM, GitOps interne, cache ni logs du lab d'origine, sur un hôte autorisé et disposable. Elle doit enregistrer :

- Révision du package, pins, dépendances obtenues et prérequis explicitement fournis.
- Commandes réellement exécutées, horodatages, codes retour, retries et écarts.
- Nœuds/API/etcd, confiance TLS, identités, transport authentifié et segmentation.
- Image construite/signée, admission positive/négative et parcours applicatif réel.
- Événement frais à chaque hop, alerte persistée, confinement et nettoyage lus en retour.
- Arrêt/reprise propre ; restauration etcd et vérification applicative/PVC dans un environnement séparé.

Tant que ce reçu n'existe pas, parler de **source conservée et contrôles bornés**, pas de déploiement portable, de disaster recovery validé ou de « one-command install ».
