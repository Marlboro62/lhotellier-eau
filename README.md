# L'Hotellier Eau pour Home Assistant

Intégration Home Assistant pour l'**espace client L'Hotellier Eau** (`serviceclients.lhotellier-eau.fr`). Elle récupère l'index de votre compteur d'eau, vos relevés et vos factures, et s'utilise dans le **tableau Énergie** (section Eau).

> Intégration non officielle, sans lien avec L'Hotellier. Elle lit les données de votre espace client avec vos identifiants.

## Capteurs

| Capteur | Description |
| --- | --- |
| Index compteur | Dernier index relevé, en m³ (pour le tableau Énergie) |
| Dernière consommation relevée | Consommation du dernier relevé, en m³, avec le total par année en attribut |
| Dernier relevé | Date et heure du dernier relevé |
| Dernière facture | Montant de la dernière facture, en €, avec l'historique en attribut |
| Date dernière facture | Date de la dernière facture |
| Mode de paiement | Diagnostic |

Les données sont mises à jour toutes les 12 heures. Les relevés de compteur sont peu fréquents : l'index ne change qu'à chaque nouveau relevé.

## Installation

1. **Paramètres › Marketplace** (ou HACS avant Home Assistant 2026.11) › menu ⋮ › **Dépôts personnalisés**.
2. Ajoutez `https://github.com/Marlboro62/lhotellier-eau`, catégorie **Intégration**.
3. Installez **L'Hotellier Eau**, puis redémarrez Home Assistant.

## Configuration

**Paramètres › Appareils et services › Ajouter une intégration › L'Hotellier Eau**, puis saisissez l'identifiant (adresse e-mail) et le mot de passe de votre espace client.

Si le mot de passe change, Home Assistant vous propose de le saisir à nouveau.

### Tableau Énergie

**Paramètres › Tableaux de bord › Énergie › Consommation d'eau › Ajouter une source d'eau**, puis choisissez le capteur **Index compteur**.

## Support

Les demandes et les problèmes passent uniquement par les [issues GitHub](https://github.com/Marlboro62/lhotellier-eau/issues).

## Licence

MIT
