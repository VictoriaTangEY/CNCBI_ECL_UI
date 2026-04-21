"""
_stage_allocation.py
-------------------
Stage allocation utilities for loan data processing.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class StageAllocation:
    """
    Stage allocation class that handles all staging criteria and logic.
    """

    def __init__(self):
        """Initialize the StageAllocation class."""
        pass

    def apply_stage_allocation(self, expo_df: pd.DataFrame, param: Dict) -> tuple:
        """
        Apply stage allocation logic to the exposure DataFrame.

        Parameters:
        - expo_df (pd.DataFrame): Exposure DataFrame
        - param (Dict): Parameter dictionary containing stage allocation parameters

        Returns:
        - Tuple[pd.DataFrame, pd.DataFrame]: (stage_1_2_df, stage_3_df)
        """
        # Get parameters with error handling
        try:
            valid_rating_table = param['valid_rating_param'].copy()
        except (KeyError, AttributeError):
            print(
                "\t\tWarning: valid_rating_param not found or invalid. Skipping rating standardization.")
            valid_rating_table = None

        try:
            notchdown_param = param['notchdown_param'].copy()
        except (KeyError, AttributeError):
            print(
                "\t\tWarning: notchdown_param not found or invalid. Skipping notchdown criteria.")
            notchdown_param = None

        # Apply each criteria in sequence with error handling
        expo_df = self._standardize_ratings(expo_df, valid_rating_table)
        expo_df = self._apply_notchdown_criteria(expo_df, notchdown_param)
        expo_df = self._apply_rating_criteria(expo_df, valid_rating_table)
        expo_df = self._apply_loan_class_criteria(expo_df)
        expo_df = self._apply_dpd_criteria(expo_df)
        expo_df = self._determine_final_stage(expo_df)

        # Separate into stage 1&2 and stage 3
        stage_1_2_df = expo_df[expo_df['final_stage'] <= 2].copy()
        stage_3_df = expo_df[expo_df['final_stage'] == 3].copy()

        # remove off-bal from stage_3
        stage_3_df = stage_3_df[stage_3_df['on_off_ind_final'] != 'OFF']
        # chk
        # stage_3_df.to_csv(
        #     "C:/Users/SA814XM/Engagement/01_CNCBI/CNCBI_ECL_Engine/02_engine_server/99_data/03_output_folder/20241231_20250723/02_interim/stage_3_df_cocochk.csv", index=False)

        return stage_1_2_df, stage_3_df

    def _standardize_ratings(self, expo_df: pd.DataFrame, valid_rating_table: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Standardize loan ratings and original ratings by adding 'G' prefix.
        Then map to corresponding grades using valid_rating_table.
        """
        try:
            if valid_rating_table is None or valid_rating_table.empty:
                print(
                    "\t\tWarning: valid_rating_table is None or empty. Skipping rating standardization.")
                # Set default values for rating columns if they don't exist
                if 'master_scale_rating' not in expo_df.columns:
                    expo_df['master_scale_rating'] = np.nan
                if 'orig_master_scale_rating' not in expo_df.columns:
                    expo_df['orig_master_scale_rating'] = np.nan
                return expo_df

            # Check if required columns exist
            required_cols = ['master_scale_rating',
                             'orig_master_scale_rating', 'segment', 'sub_segment']
            missing_cols = [
                col for col in required_cols if col not in expo_df.columns]
            if missing_cols:
                print(
                    f"\t\tWarning: Missing required columns for rating standardization: {missing_cols}. Skipping.")
                return expo_df

            # Create temporary columns for merging with 'G' prefix
            expo_df['master_scale_rating_temp'] = (
                expo_df['master_scale_rating']
                .astype(str)
                .str.zfill(2)
                .apply(lambda x: f"G{x}")
            )

            expo_df['orig_master_scale_rating_temp'] = (
                expo_df['orig_master_scale_rating']
                .astype(str)
                .str.zfill(2)
                .apply(lambda x: f"G{x}")
            )

            # Map loan_rating to corresponding grade
            merged_loan = pd.merge(
                expo_df,
                valid_rating_table,
                left_on=['segment', 'sub_segment', 'master_scale_rating_temp'],
                right_on=['segment', 'sub_segment', 'rating'],
                how='left'
            )

            # Convert to numeric safely, handling NaN values
            expo_df['master_scale_rating'] = pd.to_numeric(
                merged_loan['rating_corresponding_grade'],
                errors='coerce'
            ).astype('Int64')  # Use pandas nullable integer type

            # Map original_rating to corresponding grade
            merged_orig = pd.merge(
                expo_df,
                valid_rating_table,
                left_on=['segment', 'sub_segment',
                         'orig_master_scale_rating_temp'],
                right_on=['segment', 'sub_segment', 'rating'],
                how='left'
            )

            # Convert to numeric safely, handling NaN values
            expo_df['orig_master_scale_rating'] = pd.to_numeric(
                merged_orig['rating_corresponding_grade'],
                errors='coerce'
            ).astype('Int64')  # Use pandas nullable integer type

            # Clean up temporary columns
            expo_df = expo_df.drop(
                columns=['master_scale_rating_temp', 'orig_master_scale_rating_temp'])

        except Exception as e:
            print(f"\t\tError in rating standardization: {e}. Skipping.")
            # Set default values if processing fails
            if 'master_scale_rating' not in expo_df.columns:
                expo_df['master_scale_rating'] = np.nan
            if 'orig_master_scale_rating' not in expo_df.columns:
                expo_df['orig_master_scale_rating'] = np.nan

        return expo_df

    def _apply_notchdown_criteria(self, expo_df: pd.DataFrame, notchdown_param: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Apply notchdown staging criteria based on rating deterioration.
        Stage 2 if rating deterioration >= mapped_notchdown threshold.
        """
        try:
            if notchdown_param is None or notchdown_param.empty:
                expo_df['notch_ind'] = np.nan
                return expo_df

            # Check if required columns exist
            required_cols = ['master_scale_rating',
                             'orig_master_scale_rating', 'segment', 'sub_segment']
            missing_cols = [
                col for col in required_cols if col not in expo_df.columns]
            if missing_cols:
                print(
                    f"\t\tWarning: Missing required columns for notchdown criteria: {missing_cols}. Skipping.")
                expo_df['notch_ind'] = np.nan
                return expo_df

            # Create temporary string columns for merging
            expo_df['master_scale_rating_temp'] = expo_df['master_scale_rating'].astype(
                str)
            notchdown_param['rating_corresponding_grade'] = notchdown_param['rating_corresponding_grade'].astype(
                str)

            # Merge with notchdown parameters
            merged = pd.merge(
                expo_df,
                notchdown_param,
                left_on=['segment', 'sub_segment', 'master_scale_rating_temp'],
                right_on=['segment', 'sub_segment',
                          'rating_corresponding_grade'],
                how='left'
            )

            # Convert to numeric for calculations (ratings are already numeric from _standardize_ratings)
            original_rating = merged['orig_master_scale_rating']
            loan_rating = merged['master_scale_rating']
            mapped_notchdown = pd.to_numeric(
                merged['sicr_notchdown'], errors='coerce')

            # Calculate rating difference
            rating_diff = original_rating - loan_rating

            # Apply notchdown criteria
            expo_df['notch_ind'] = np.where(
                (rating_diff >= mapped_notchdown) & (
                    ~rating_diff.isna()) & (~mapped_notchdown.isna()),
                2,  # Stage 2
                np.where(
                    (rating_diff < mapped_notchdown) & (
                        ~rating_diff.isna()) & (~mapped_notchdown.isna()),
                    1,  # Stage 1
                    np.nan  # Keep as NA if any input is NA
                )
            )

            # Clean up temporary column
            expo_df = expo_df.drop(columns=['master_scale_rating_temp'])

        except Exception as e:
            print(f"\t\tError in notchdown criteria: {e}. Skipping.")
            expo_df['notch_ind'] = np.nan

        return expo_df

    def _apply_rating_criteria(self, expo_df: pd.DataFrame, valid_rating_table: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Apply rating-based staging criteria using valid_rating_table.
        """
        try:
            if valid_rating_table is None or valid_rating_table.empty:
                print(
                    "\t\tWarning: valid_rating_table is None or empty. Skipping rating criteria.")
                expo_df['rating_ind'] = np.nan
                return expo_df

            # Check if required columns exist
            required_cols = ['master_scale_rating', 'segment', 'sub_segment']
            missing_cols = [
                col for col in required_cols if col not in expo_df.columns]
            if missing_cols:
                print(
                    f"\t\tWarning: Missing required columns for rating criteria: {missing_cols}. Skipping.")
                expo_df['rating_ind'] = np.nan
                return expo_df

            # Create temporary string column for merging
            expo_df['master_scale_rating_temp'] = expo_df['master_scale_rating'].astype(
                str)
            valid_rating_table['rating_corresponding_grade'] = valid_rating_table['rating_corresponding_grade'].astype(
                str)

            # Merge with valid rating table
            merged = pd.merge(
                expo_df,
                valid_rating_table,
                left_on=['segment', 'sub_segment', 'master_scale_rating_temp'],
                right_on=['segment', 'sub_segment',
                          'rating_corresponding_grade'],
                how='left'
            )

            expo_df['rating_ind'] = merged['grade_corresponding_stage']

            # Clean up temporary column
            expo_df = expo_df.drop(columns=['master_scale_rating_temp'])

        except Exception as e:
            print(f"\t\tError in rating criteria: {e}. Skipping.")
            expo_df['rating_ind'] = np.nan

        return expo_df

    def _apply_loan_class_criteria(self, expo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply loan class staging criteria:
        - SM, SS: Stage 2
        - DF, LS: Stage 3
        - Others: Stage 1
        """
        try:
            if 'loan_class_cd' not in expo_df.columns:
                print(
                    "\t\tSkipping loan class criteria.")
                expo_df['loan_class_ind'] = np.nan
                return expo_df

            conditions = [
                expo_df['loan_class_cd'].isin(['SM', 'SS']),
                expo_df['loan_class_cd'].isin(['DF', 'LS'])
            ]
            expo_df['loan_class_ind'] = np.select(
                conditions, [2, 3], default=1)

        except Exception as e:
            print(f"\t\tError in loan class criteria: {e}. Skipping.")
            expo_df['loan_class_ind'] = np.nan

        return expo_df

    def _apply_dpd_criteria(self, expo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply days past due staging criteria:
        - 30-89 days: Stage 2
        - 90+ days: Stage 3
        - <30 days: Stage 1
        """
        try:
            if 'days_pastdue' not in expo_df.columns:
                print(
                    "\t\tSkipping DPD criteria.")
                expo_df['dpd_ind'] = np.nan
                return expo_df

            conditions = [
                (expo_df['days_pastdue'] >= 30) & (
                    expo_df['days_pastdue'] < 90),
                (expo_df['days_pastdue'] >= 90)
            ]
            expo_df['dpd_ind'] = np.select(conditions, [2, 3], default=1)

        except Exception as e:
            print(f"\t\tError in DPD criteria: {e}. Skipping.")
            expo_df['dpd_ind'] = np.nan

        return expo_df

    def _determine_final_stage(self, expo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Determine final stage based on maximum of all indicators.
        """
        try:
            indicator_cols = ['notch_ind', 'rating_ind',
                              'loan_class_ind', 'dpd_ind']

            # Check which indicator columns exist
            existing_cols = [
                col for col in indicator_cols if col in expo_df.columns]
            if not existing_cols:
                print(
                    "\t\tWarning: No indicator columns found. Setting all records to Stage 1.")
                expo_df['final_stage'] = 1
                return expo_df

            # Convert all indicator columns to numeric, coercing errors to NaN
            for col in existing_cols:
                expo_df[col] = pd.to_numeric(expo_df[col], errors='coerce')

            # Calculate final stage as maximum of existing indicators and convert to int
            expo_df['final_stage'] = expo_df[existing_cols].max(
                axis=1).fillna(1).astype(int)

            # Clean up temporary indicator columns
            expo_df = expo_df.drop(columns=existing_cols)

        except Exception as e:
            print(
                f"\t\tError in determining final stage: {e}. Setting all records to Stage 1.")
            expo_df['final_stage'] = 1

        return expo_df
