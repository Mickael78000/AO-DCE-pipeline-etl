# Contrat Métier : Règle de Consolidation `procedure_type`

## Référence
`CONSOLIDATION-RULE-001 — Qualification des Procédures de Marchés Publics`

## Version
1.0 — 14 mai 2026

---

## 1. Objectif

Transformer la valeur extraite `procedure_type` en une qualification consolidée unique, cohérente juridiquement et traçable, en détectant et gérant les incohérences entre la source brute et les contraintes juridiques fortes.

---

## 2. Principes Fondamentaux

### 2.1 Distinction Source / Consolidation

| Niveau | Description | Usage |
|--------|-------------|-------|
| **Source** (`procedure_source`) | Valeur lue dans le HTML ou extraite par le pipeline | Trace d'audit, non décisionnelle |
| **Consolidation** (`procedure_consolidee`) | Qualification retenue après analyse croisée | Valeur métier utilisée pour la classification juridique |

### 2.2 Hiérarchie des Indices (priorité décroissante)

1. **Contraintes juridiques fortes**
   - Montant estimé HT
   - Seuil applicable HT (selon type d'acheteur, nature du marché, régime)
   - Type d'acheteur (autorité centrale, collectivité, établissement public...)
   - Nature du marché (services, fournitures, travaux)
   - Régime juridique (droit commun / défense et sécurité)
   - Preuve de publication (JOUE, BOAMP, plateforme nationale)

2. **Indices explicites de source**
   - `procedure_type` extrait
   - Badges HTML visibles
   - Libellés textuels directs

3. **Indices contextuels**
   - Titre du marché
   - Acheteur et fonction publique
   - Plateforme source
   - Caractère stratégique ou sensible

4. **Indices faibles**
   - Mots-clés isolés
   - Inférences indirectes

### 2.3 Règle d'Or

> Une valeur source explicite **n'est pas souveraine** si elle contredit plusieurs indices de contrainte juridique forte.

---

## 3. Seuils Applicables 2026

### 3.1 Seuils de Procédure Formalisée

| Type d'Acheteur | Nature du Marché | Seuil MAPA | Seuil Formalisé |
|-----------------|------------------|------------|-----------------|
| Autorité publique centrale (État) | Services | 40 000 € HT | **140 000 € HT** |
| Autorité publique centrale (État) | Fournitures | 40 000 € HT | **140 000 € HT** |
| Autres pouvoirs adjudicateurs | Services | 40 000 € HT | **216 000 € HT** |
| Autres pouvoirs adjudicateurs | Fournitures | 40 000 € HT | **216 000 € HT** |
| Travaux (tous acheteurs) | Travaux | 40 000 € HT | **5 382 000 € HT** |
| **Défense et Sécurité** | Services/Fournitures | 40 000 € HT | **443 000 € HT** |

### 3.2 Règle de Calcul du Ratio

```
ratio = montant_estime_ht / seuil_applicable_ht
```

- Si `ratio > 1.0` : le montant dépasse le seuil formalisé
- Si `ratio > 10.0` : le montant dépasse très largement le seuil (alerte forte)

---

## 4. Matrice de Décision

### 4.1 Scénario A : Source cohérente avec contraintes

| Condition | Action |
|-----------|--------|
| `procedure_source = MAPA` ET `montant < seuil MAPA` | `procedure_consolidee = MAPA_SOUS_SEUIL` |
| `procedure_source = formalisee` ET `preuve_joue = oui` | `procedure_consolidee = JOUE_PROUVE` |
| `procedure_source = formalisee` ET `preuve_joue = non` | `procedure_consolidee = FORMALISEE_SANS_PREUVE_JOUE` |

### 4.2 Scénario B : Source incohérente (conflit détecté)

| Condition | Action | Motif de Conflit |
|-----------|--------|------------------|
| `procedure_source = MAPA` ET `montant >> seuil` | `procedure_consolidee = FORMALISEE_REQUISE` | "Montant très supérieur au seuil applicable, incompatible avec MAPA" |
| `procedure_source = MAPA` ET `regime = defense_securite` | `procedure_consolidee = FORMALISEE_REQUISE` | "MAPA incompatible avec régime défense et sécurité" |
| `procedure_source = negociee` ET `montant > seuil formalise` | `procedure_consolidee = FORMALISEE_NEGOCIEE` | "Procédure négociée mais montant supérieur au seuil MAPA" |

### 4.3 Scénario C : Indétermination

| Condition | Action |
|-----------|--------|
| `procedure_source` vide ou inconnu | `procedure_consolidee = INDETERMINE` |
| Conflits multiples non résolubles | `procedure_consolidee = INDETERMINE` |

---

## 5. Format de Sortie

### 5.1 Colonnes CSV Enrichies

| Colonne | Type | Description |
|---------|------|-------------|
| `procedure_source` | string | Valeur lue dans la source HTML |
| `source_procedure_evidence` | string | Citation ou sélecteur de la source |
| `procedure_consolidee` | string | Qualification retenue après analyse |
| `procedure_regime` | string | `defense_securite` ou `marches_ordinaires` |
| `conflit_coherence` | enum(oui,non) | Indication de conflit détecté |
| `motif_conflit` | string | Explication factuelle du conflit |
| `seuil_applicable_ht` | integer | Seil de formalisation en € HT |
| `montant_estime_ht` | integer | Montant du marché en € HT |
| `ratio_montant_sur_seuil` | float | Ratio montant / seuil |
| `priorite_juridique` | enum | `seuil`, `regime`, `preuve_joue`, `source_explicite`, `indetermine` |
| `niveau_confiance` | enum | `fort`, `moyen`, `faible` |
| `procedure_verdict` | string | Phrase expliquant le rejet ou la validation de la source |
| `verdict_final` | string | Conclusion unique et exploitable |
| `notes_consolidation` | string | Compléments si nécessaire |

### 5.2 Valeurs Possibles pour `procedure_consolidee`

- `MAPA_SOUS_SEUIL`
- `JOUE_PROUVE`
- `FORMALISEE_SANS_PREUVE_JOUE`
- `FORMALISEE_NEGOCIEE`
- `FORMALISEE_REQUISE`
- `INDETERMINE`

---

## 6. Exemples d'Application

### Exemple 1 : DAF_2025_001001 (Marché Cloud MINARM)

**Données source :**
- `procedure_source = MAPA`
- `montant = 18 020 000 € HT`
- `type_acheteur = etat`
- `categorie_regime = defense_securite`

**Analyse :**
- Seuil applicable (défense/services) = 443 000 € HT
- Ratio = 40,68 (très supérieur au seuil)
- Conflit : MAPA incompatible avec montant et régime

**Sortie :**
```json
{
  "procedure_source": "MAPA",
  "procedure_consolidee": "FORMALISEE_REQUISE",
  "conflit_coherence": "oui",
  "motif_conflit": "Montant 18,02 M€ HT très supérieur au seuil applicable ; incohérence forte avec procédure adaptée",
  "seuil_applicable_ht": 443000,
  "montant_estime_ht": 18020000,
  "ratio_montant_sur_seuil": 40.68,
  "priorite_juridique": "seuil",
  "procedure_verdict": "La procédure source MAPA a été lue mais rejetée comme qualification finale",
  "verdict_final": "FORMALISEE_REQUISE - procédure source MAPA rejetée comme qualification finale"
}
```

---

## 7. Implémentation

Le script `consolidate_procedure.py` implémente ce contrat métier et applique la consolidation à l'ensemble du fichier `final-v3-consolidated-classified-juridique-v9.csv`.

---

## 8. Traçabilité et Audit

Chaque ligne du CSV de sortie contient :
- La **valeur source** (inchangée, pour audit)
- La **valeur consolidée** (décisionnelle)
- Le **motif de conflit** si rejet de la source
- Le **ratio montant/seuil** (preuve chiffrée de la décision)

Cette structure garantit la traçabilité complète entre extraction brute et qualification juridique finale.

---

## Références Juridiques

- Code de la commande publique, art. R2122-1 à R2122-8 (seuils MAPA et formalisés)
- Code de la commande publique, art. L2125-1 et R2125-1 (régime défense et sécurité)
- Arrêté du 28 décembre 2025 fixant les seuils des marchés publics pour 2026

---

**Document validé pour implémentation en production.**
