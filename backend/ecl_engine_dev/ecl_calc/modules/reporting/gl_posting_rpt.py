import pandas as pd
import numpy as np
import time


class GlPostingRpt:

    def __init__(self, context, ecl_df):
        self.outResultPath = context.outResultPath
        self.outInterimPath = context.outInterimPath
        self.rpt_dt = context.data_yymm
        self.ecl_df = ecl_df  # use the loaded data from service

    def process_all(self):
        self.summary()
        self.gl_posting()
        return

    def summary(self):
        '''
        Prepare GL posting specific summary columns:
        - coa_prod_group (based on stage and coa_prod_gp1)
        - group, group1, group2, group3 (based on elim and entity1)

        Note: General columns (ecl_hke_m, class, stage, entity1, profit_centre_1, coa_prod_gp1)
        are now added in output_handler.add_cols()
        '''
        # Select only required columns (lowercase) from the dataframe
        required_columns = [
            'class',
            'coa',
            'coa_prod_gp1',
            'product1',
            'c800',
            'entity1',
            'entity2',
            'coa_entity',
            'bu1',
            'bu3',
            'bu4',
            'ceo1',
            'ceo2',
            'elim',
            'interco_cd',
            'stage',
            'cur_bal_hke_m',
            'ead_hke_m',
            'ecl_hke_m'
        ]

        # Filter to only include columns that exist in the dataframe
        available_columns = [
            col for col in required_columns if col in self.ecl_df.columns]
        df = self.ecl_df[available_columns].copy()

        # Ensure elim is string format (output_handler generates elim as int)
        if 'elim' in df.columns:
            df['elim'] = df['elim'].astype(str).str.strip()

        # coa_prod_group mapping based on stage and coa_prod_gp1
        # Create mapping dictionaries for Stage 1/2 and Stage 3
        mapping_stage_12 = {
            'LOA': '01.LOA',
            'LOA-Card': '02.LOA-Card',
            'LOA-TBS': '03.LOA-TBS',
            'FVOCI_5851': '04.FVOCI_5851',
            'FVOCI_5852': '05.FVOCI_5852',
            'FVOCI_1304': '06.FVOCI_1304',
            'MM_5820': '07.MM_5820',
            'MM': '07.MM_5820',
            'MM_8216': '08.MM_8216',
            'MM_REPO2902': '09.MM_REPO2902',
            'MM_REPO5820': '10.MM_REPO5820',
            'MM_REV5212': '11.MM_REV5212',
            'MM-Rev Repo': '11.MM_REV5212',
            'MM_REV5288': '12.MM_REV5288',
            'MM_REV5289': '13.MM_REV5289',
            'MM-CSA': '14.MM-CSA',
            'MM-AdvBk': '15.MM-AdvBk',
            'NOSTRO': '16.NOSTRO',
            'OTHER AC_FXA': '17.OTHER AC_FXA',
            'OTHER AC': '18.OTHER AC - BR/TR',
            'Fin Gua': '19.Fin Gua',
            'LOA Com+Fact': '20.LOA Com+Fact',
            'AC Invest': '21.Amortised Cost Inv'
        }

        mapping_stage_3 = mapping_stage_12.copy()
        mapping_stage_3['OTHER AC'] = '17.OTHER AC_FXA'  # Override for Stage 3

        # Apply mapping based on stage using vectorized operations
        # First map all records using Stage 1/2 mapping
        df['coa_prod_group'] = df['coa_prod_gp1'].map(
            mapping_stage_12).fillna('')

        # Then override Stage 3 records with Stage 3 mapping
        stage_3_mask = df['stage'] == 'Stage 3'
        df.loc[stage_3_mask, 'coa_prod_group'] = df.loc[stage_3_mask,
                                                        'coa_prod_gp1'].map(mapping_stage_3).fillna('')

        # mapping diagnostics (disabled for clean output)

        # Add GL posting specific group columns
        df = self._add_group_columns(df)

        # Export summary report (same as reporting_ecl_result_summary.xlsx)
        df.to_excel(
            self.outResultPath / "reporting_ecl_result_summary.xlsx",
            index=False,
            engine='openpyxl'
        )

        # store processed
        self.processed_df = df

        return

    def _add_group_columns(self, df):
        """
        Add GL posting specific group columns: group, group1, group2, group3
        """
        # group: if elim=0,"CNCBI-GROUP"else ""
        df['group'] = np.where(df['elim'] == '0', 'CNCBI-GROUP', '')

        # group1: if entity1="CNCBI","CNCBI-HK", else entity1
        df['group1'] = np.where(df['entity1'] == 'CNCBI',
                                'CNCBI-HK', df['entity1'])

        # group2: if elim=1,"CNCBI-GROUP ELIM", else ""
        df['group2'] = np.where(df['elim'] == '1', 'CNCBI-GROUP ELIM', '')

        # group3: =IF(AND(elim=1,entity1="CNCBI"),"CNCBI-HK ELIM",IF(elim=1,entity1&" ELIM",""))
        df['group3'] = np.where(
            (df['elim'] == '1') & (df['entity1'] == 'CNCBI'),
            'CNCBI-HK ELIM',
            np.where(df['elim'] == '1', df['entity1'] + ' ELIM', '')
        )

        return df

    def gl_posting(self):

        # Ensure processed_df exists
        df = getattr(self, 'processed_df', None)
        if df is None:
            self.summary()
            df = self.processed_df

        # Prepare constants
        classes = ['Loans', 'Non-loans']
        prod_groups = [
            '01.LOA', '02.LOA-Card', '03.LOA-TBS', '04.FVOCI_5851', '05.FVOCI_5852',
            '06.FVOCI_1304', '07.MM_5820', '08.MM_8216', '09.MM_REPO2902', '10.MM_REPO5820',
            '11.MM_REV5212', '12.MM_REV5288', '13.MM_REV5289', '14.MM-CSA', '15.MM-AdvBk',
            '16.NOSTRO', '17.OTHER AC_FXA', '18.OTHER AC - BR/TR', '19.Fin Gua', '20.LOA Com+Fact',
            '21.Amortised Cost Inv'
        ]
        stages = ['Stage 1', 'Stage 2', 'Stage 3']

        # Template multiindex and empty pivot
        index_template = pd.MultiIndex.from_product(
            [classes, prod_groups], names=['class', 'coa_prod_group'])

        def empty_pivot():
            return pd.DataFrame(0.0, index=index_template, columns=stages)

        # Table definitions: map table label -> (column, value)
        table_map = {
            'CNCBI-GROUP': ('group', 'CNCBI-GROUP'),
            'CNCBI-HK': ('group1', 'CNCBI-HK'),
            'CNCBI-HK ELIM': ('group3', 'CNCBI-HK ELIM'),
            'CNCBI-GROUP ELIM': ('group2', 'CNCBI-GROUP ELIM'),
            'SG Branch': ('group1', 'SG Branch'),
            'SG Branch ELIM': ('group3', 'SG Branch ELIM'),
            'LA Branch': ('group1', 'LA Branch'),
            'LA Branch ELIM': ('group3', 'LA Branch ELIM'),
            'NY Branch': ('group1', 'NY Branch'),
            'NY Branch ELIM': ('group3', 'NY Branch ELIM'),
            'MC Branch': ('group1', 'MC Branch'),
            'MC Branch ELIM': ('group3', 'MC Branch ELIM'),
            'CBI China': ('group1', 'CBI China'),
            'VIEWCON': ('group1', 'Viewcon'),
            'VIEWCON ELIM': ('group3', 'Viewcon ELIM'),
            'HKCBF': ('group1', 'HKCBF'),
            'HKCBF ELIM': ('group3', 'HKCBF ELIM'),
        }

        gl_pivots = {}
        # Precompute amount
        df = df.copy()
        df['amount'] = -pd.to_numeric(df['ecl_hke_m'],
                                      errors='coerce').fillna(0.0) * 1_000_000

        # amount diagnostics (disabled for clean output)

        for label, (col, val) in table_map.items():
            sub = df[df[col] == val][[
                'class', 'coa_prod_group', 'stage', 'amount']]
            # table build diagnostics (disabled for clean output)
            if sub.empty:
                gl_pivots[label] = empty_pivot()
                continue
            # group & pivot using vectorized operations
            grouped = sub.groupby(['class', 'coa_prod_group', 'stage'], as_index=False)[
                'amount'].sum()
            piv = grouped.pivot_table(
                index=['class', 'coa_prod_group'],
                columns='stage',
                values='amount',
                aggfunc='sum',
                fill_value=0.0
            )
            # Reindex to template
            piv = piv.reindex(index_template, fill_value=0.0)
            # Ensure all stage columns
            for c in stages:
                if c not in piv.columns:
                    piv[c] = 0.0
            piv = piv[stages]
            gl_pivots[label] = piv

        self.gl_pivots = gl_pivots

        # Export to Excel
        file_base = 'reporting_ecl_gl_posting'
        out_path = self.outResultPath / f"{file_base}.xlsx"
        # export path info (disabled for clean output)

        try:
            with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
                sheet_name = 'GL_Posting'
                current_row = 0
                for label, table in self.gl_pivots.items():
                    # writing table info (disabled for clean output)
                    # Title row with proper formatting
                    title_df = pd.DataFrame({'Table Name': [label]})
                    title_df.to_excel(
                        writer, sheet_name=sheet_name, startrow=current_row, index=False, header=True
                    )
                    current_row += 2  # Skip one row after title
                    # Column headers + data
                    out_df = table.reset_index()
                    out_df.to_excel(
                        writer, sheet_name=sheet_name, startrow=current_row, index=False, header=True
                    )
                    current_row += len(out_df) + 3  # spacing between tables
        except Exception as e:
            # single sheet failed (logged silently)
            # Fallback: one table per sheet
            with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
                for label, table in self.gl_pivots.items():
                    out_df = table.reset_index()
                    safe_name = label[:31]
                    # writing separate sheet info (disabled for clean output)
                    out_df.to_excel(
                        writer, sheet_name=safe_name, index=False
                    )

        return
