import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import csv
import importlib.util

# Step 1: Function to Locate the CODE Directory Dynamically (Works from Any Depth)
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from script's directory
    while current_dir and os.path.basename(current_dir) != "CODE":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Stop if we reach the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # Now 'CODE' directory is located

# Step 2: Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# Step 3: Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)

# Update directories dynamically
cleaned_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Cleaned")
interleaved_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Interleaved")

# Ensure the output directory exists
os.makedirs(interleaved_directory, exist_ok=True)

# def safe_division(numerator, denominator):
#     return numerator / denominator if denominator != 0 else 0

# Process each file in the cleaned directory
for file_name in os.listdir(cleaned_directory):
    cleaned_file_path = os.path.join(cleaned_directory, file_name)
    
    # Check if the file is a CSV
    if file_name.endswith('.csv'):
        try:
            # Load the dataset
            signals_df_rcb = pd.read_csv(cleaned_file_path, low_memory=False)
            
            entries_1_rcb = []
            entries_2_rcb = []
            
            # Process rows
            for _, row in signals_df_rcb.iterrows():
                # --- Entry 1 Calculations ---
                # Common Variables
                call_id = row['IDRSSD']
                date_id = row['RCON9999']
                CERT = row['FDIC Certificate Number']
                #####-----Schedule RC-----#####
                ###---Cash
                RC_item1_entry1 = row['RCON0081'] + row['RCON0071']
                ###---Securities
                RC_item2_entry1 = (
                    row['RCONJJ34'] + row['RCON1773'] + row['RCONJA22'] if row['RCON9999'] >= 20190331 else row['RCON1754'] + row['RCON1773']
                ) ##--HTM securities (from Schedule RC-B, column A [less Schedule RI-B Part II, Item 7, column B])
                ###---Loans and lease financing receivables (from Schedule RC-C)
                RC_item4_entry1 = row['RCON5369'] + row['RCONB529']
                ###---Trading assets (from Schedule RC-D)
                RC_item5_entry1 = row['RCON3545']
                ###---Other real estate owned (from Schedule RC-M)
                RC_item7_entry1 = row['RCON2150']
                ###---Intangible assets (from Schedule RC-M)
                RC_item10_entry1 = (
                    row['RCON2143'] if row['RCON9999'] >= 20180630 else row['RCON3163'] + row['RCON0426']
                )
                ###---Total assets---###
                RC_item12_entry1 = (
                    row['RCON2170'] - row['RCONJA22'] + row['RCON3123'] if row['RCON9999'] >= 20180331 else row['RCON2170'] + row['RCON3123']
                )
                ###---Total liabilities---###
                RC_item14_entry1 = row['RCONB993'] + row['RCONB995']
                RC_item21_entry1 = row['RCON2948'] + row['RCON3123']
                ###---Total equity capital---###
                RC_item28_entry1 = (
                    row['RCONG105'] - row['RCONJA22'] if row['RCON9999'] >= 20180331 else row['RCONG105']
                )
                #####-----Schedule RC-B-----#####
                ###---Government Securities
                RCB_item2_htm_ac_entry1 = (
                    row['RCONHT50'] if row['RCON9999'] > 20180331 else row['RCON1289'] + row['RCON1294']
                )
                RCB_item2_htm_fv_entry1 = (
                    row['RCONHT51'] if row['RCON9999'] > 20180331 else row['RCON1290'] + row['RCON1295']
                )
                RCB_item2_afs_fv_entry1 = (
                    row['RCONHT53'] if row['RCON9999'] > 20180331 else row['RCON1293'] + row['RCON1298']
                )
                
                ##--Mortgage-backed Securities - Item 4.a--##
                RCB_item4a_htm_ac_entry1 = row['RCONG300'] + row['RCONG304'] + row['RCONG308']
                RCB_item4a_htm_fv_entry1 = row['RCONG301'] + row['RCONG305'] + row['RCONG309']
                RCB_item4a_afs_fv_entry1 = row['RCONG303'] + row['RCONG307'] + row['RCONG311']
                
                ##--Item 4.b--##
                RCB_item4b_htm_ac_entry1 = row['RCONG312'] + row['RCONG316'] + row['RCONG320']
                RCB_item4b_htm_fv_entry1 = row['RCONG313'] + row['RCONG317'] + row['RCONG321']
                RCB_item4b_afs_fv_entry1 = row['RCONG315'] + row['RCONG319'] + row['RCONG323']
                
                ###---Item 4 - Total---###
                ##--Item 4.c--##
                # Item 4.c.1
                RCB_item4c1_htm_ac_entry1 = (
                    row['RCONK142'] + row['RCONK146'] if row['RCON9999'] > 20110331 else row['RCONG324']
                )
                RCB_item4c1_htm_fv_entry1 = (
                    row['RCONK143'] + row['RCONK147'] if row['RCON9999'] > 20110331 else row['RCONG325']
                )
                RCB_item4c1_afs_fv_entry1 = (
                    row['RCONK145'] + row['RCONK149'] if row['RCON9999'] > 20110331 else row['RCONG327']
                )
                
                # Item 4.c.2
                RCB_item4c2_htm_ac_entry1 = (
                    row['RCONK150'] + row['RCONK154'] if row['RCON9999'] > 20110331 else row['RCONG328']
                )
                RCB_item4c2_htm_fv_entry1 = (
                    row['RCONK151'] + row['RCONK155'] if row['RCON9999'] > 20110331 else row['RCONG329']
                )
                RCB_item4c2_afs_fv_entry1 = (
                    row['RCONK153'] + row['RCONK157'] if row['RCON9999'] > 20110331 else row['RCONG331']
                )

                # Item 4.c
                RCB_item4c_htm_ac_entry1 = RCB_item4c1_htm_ac_entry1 + RCB_item4c2_htm_ac_entry1
                RCB_item4c_htm_fv_entry1 = RCB_item4c1_htm_fv_entry1 + RCB_item4c2_htm_fv_entry1
                RCB_item4c_afs_fv_entry1 = RCB_item4c1_afs_fv_entry1 + RCB_item4c2_afs_fv_entry1
                
                # Item 4 - Total
                RCB_item4_htm_ac_entry1 = RCB_item4a_htm_ac_entry1 + RCB_item4b_htm_ac_entry1 + RCB_item4c_htm_ac_entry1
                ###---Memoranda Items
                # Item M.2.a - Total
                RCB_itemM2a_entry1 = row['RCONA549'] + row['RCONA550'] + row['RCONA551'] + row['RCONA552'] + row['RCONA553'] + row['RCONA554']
                RCB_itemM2b_entry1 = row['RCONA555'] + row['RCONA556'] + row['RCONA557'] + row['RCONA558'] + row['RCONA559'] + row['RCONA560']
                #####-----Schedule RC-E-----#####
                ###---Nontransaction accounts
                # Savings deposits
                RCE_savings_entry1 = row['RCON6810'] + row['RCON0352']
                RCE_time_depo_250K_entry1 = row['RCON6648'] + row['RCONJ473']
                #####-----Schedule RC-R Part I-----#####
                ###---Common Equity Tier 1 Capital
                RCB_item4c2_htm_ac_xyzentry1 = (
                    row['RCOAP859'] + row['RCOAP858'] if row['RCON9999'] >= 20200331 and row['RCOAP858'] != '' else row['RCOAP859'] + row['RCOAP858']
                )
                RCB_item4c2_htm_fv_abcentry1 = (
                    row['RCOAP859'] + row['RCOAP858'] if row['RCON9999'] >= 20200331 and row['RCOAP858'] != '' else row['RCOAP859'] + row['RCOAP858']
                )
                RCRI_CET1_Basel_entry1 = row['RCOAP793']
                ###---Risk-Weighted Assets
                RWA_Basel_entry1 = row['RCOAA223'] + (0.15*row['RCONA554'] + 0.1*row['RCONA553'] + 0.08*row['RCONA552'] + 0.15*row['RCONA560'] + 0.1*row['RCONA559'] + 0.08*row['RCONA558'])
                # RWA_adjustment_entry1 = (row['RCONA554'] + row['RCONA553'] + row['RCONA552'] + row['RCONA560'] + row['RCONA559'] + row['RCONA558'])
                RWA_adjustment_entry1 = (row['RCONA554'] + row['RCONA553']+row['RCONA560']+row['RCONA559'])
                ###---ZRWA
                ZRWA_Ratio_entry1 = (row['RCOND962']+row['RCOND967'])/(row['RCON1754']+row['RCON1773']) if row['RCON9999'] >= 20150331 and (row['RCON1754']+row['RCON1773']) != 0 else (row['RCONB603']+row['RCONB608'])/(row['RCON1754']+row['RCON1773']) if row['RCON9999'] < 20150331 and row['RCON1754']+row['RCON1773'] != 0 else 0
                RCRI_ZRWA_RWA3 = row['RCOND987'] / RWA_Basel_entry1 if row['RCON9999'] >= 20150331 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0
                RCRI_ZRWA_RWA4 = (row['RCOND987']-(ZRWA_Ratio_entry1*RWA_adjustment_entry1)) / RWA_Basel_entry1 if row['RCON9999'] >= 20150331 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0
                
                entry1 = {
                    'IDRSSD': call_id,
                    'RCON9999': date_id,
                    'CERT': CERT,
                    #####---------Scheduel RC-B---------#####
                    ####----Group-specific Ratios----####
                    ###---U.S Treasury securities
                    'RCB-0211-1754': row['RCON0211'] / row['RCON1754'] if row['RCON1754'] != 0 else 0,
                    'RCB-1287-1773': row['RCON1287'] / row['RCON1773'] if row['RCON1773'] != 0 else 0,
                    'RCB-item4-1754': RCB_item4_htm_ac_entry1 / row['RCON1754'] if row['RCON1754'] != 0 else 0,
                    ###---U.S. Government agency and sponsored agency obligations
                    'RCB-HT50-1754': RCB_item2_htm_ac_entry1 / row['RCON1754'] if row['RCON1754'] != 0 else 0,
                    'RCB-HT53-1773': RCB_item2_afs_fv_entry1 / row['RCON1773'] if row['RCON1773'] != 0 else 0,
                    ###---Securities issued by states and political subdivisions
                    'RCB-8496-1754': row['RCON8496'] / row['RCON1754'] if row['RCON1754'] != 0 else 0,
                    'RCB-8499-1773': row['RCON8499'] / row['RCON1773'] if row['RCON1773'] != 0 else 0,
                    ###---Mortgage-backed securities---###
                    ##--Residential mortgage pass-through securities
                    'RCB-G300-item4a': row['RCONG300'] / RCB_item4a_htm_ac_entry1 if RCB_item4a_htm_ac_entry1 != 0 else 0,
                    'RCB-G304-Item4a': row['RCONG304'] / RCB_item4a_htm_ac_entry1 if RCB_item4a_htm_ac_entry1 != 0 else 0,
                    'RCB-G308-Item4a': row['RCONG308'] / RCB_item4a_htm_ac_entry1 if RCB_item4a_htm_ac_entry1 != 0 else 0,
                    'RCB-G303-item4a': row['RCONG303'] / RCB_item4a_afs_fv_entry1 if RCB_item4a_afs_fv_entry1 != 0 else 0,
                    'RCB-G307-Item4a': row['RCONG307'] / RCB_item4a_afs_fv_entry1 if RCB_item4a_afs_fv_entry1 != 0 else 0,
                    'RCB-G311-Item4a': row['RCONG311'] / RCB_item4a_afs_fv_entry1 if RCB_item4a_afs_fv_entry1 != 0 else 0,
                    ##--Other residential mortgage-backed securities
                    'RCB-G312-item4b': row['RCONG312'] / RCB_item4b_htm_ac_entry1 if RCB_item4b_htm_ac_entry1 != 0 else 0,
                    'RCB-G316-Item4b': row['RCONG316'] / RCB_item4b_htm_ac_entry1 if RCB_item4b_htm_ac_entry1 != 0 else 0,
                    'RCB-G320-Item4b': row['RCONG320'] / RCB_item4b_htm_ac_entry1 if RCB_item4b_htm_ac_entry1 != 0 else 0,
                    'RCB-G315-item4b': row['RCONG315'] / RCB_item4b_afs_fv_entry1 if RCB_item4b_afs_fv_entry1 != 0 else 0,
                    'RCB-G319-Item4b': row['RCONG319'] / RCB_item4b_afs_fv_entry1 if RCB_item4b_afs_fv_entry1 != 0 else 0,
                    'RCB-G323-Item4b': row['RCONG323'] / RCB_item4b_afs_fv_entry1 if RCB_item4b_afs_fv_entry1 != 0 else 0,
                    ##--Commercial mortgage-backed securities
                    #-Commercial mortgage pass-through securities
                    'RCB-Item4c1-Item4c': RCB_item4c1_htm_ac_entry1 / RCB_item4c_htm_ac_entry1 if RCB_item4c_htm_ac_entry1 != 0 else 0,
                    #-Other commercial MBS
                    'RCB-Item4c2-Item4c': RCB_item4c2_htm_ac_entry1 / RCB_item4c_htm_ac_entry1 if RCB_item4c_htm_ac_entry1 != 0 else 0,
                    ####----Domain-specific Ratios----####
                    'RCB-0213-0211': row['RCON0213'] / row['RCON0211'] if row['RCON0211'] != 0 else 0,
                    'RCB-HT51-HT50': RCB_item2_htm_fv_entry1 / RCB_item2_htm_ac_entry1 if RCB_item2_htm_ac_entry1 != 0 else 0,
                    'RCB-8497-8496': row['RCON8497'] / row['RCON8496'] if row['RCON8496'] != 0 else 0,
                    'RCB-item4a-fv2ac': RCB_item4a_htm_fv_entry1 / RCB_item4a_htm_ac_entry1 if RCB_item4a_htm_ac_entry1 != 0 else 0,
                    'RCB-item4b-fv2ac': RCB_item4b_htm_fv_entry1 / RCB_item4b_htm_ac_entry1 if RCB_item4b_htm_ac_entry1 != 0 else 0,
                    'RCB-item4c-fv2ac': RCB_item4c_htm_fv_entry1 / RCB_item4c_htm_ac_entry1 if RCB_item4c_htm_ac_entry1 != 0 else 0,
                    ###---Item M.2.a (securities issued by the U.S. Treasury, U.S. Governmental agencies and states and plitical subdivisions in the U.S with a remaining maturity or next repricing date of:)
                    'RCB-A549-itemM2a': row['RCONA549'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    'RCB-A550-itemM2a': row['RCONA550'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    'RCB-A551-itemM2a': row['RCONA551'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    'RCB-A552-itemM2a': row['RCONA552'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    'RCB-A553-itemM2a': row['RCONA553'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    # Over 15 years
                    'RCB-A554-itemM2a': row['RCONA554'] / RCB_itemM2a_entry1 if RCB_itemM2a_entry1 != 0 else 0,
                    ###---Item M.2.b (Mortgage pass-through securities backed by closed-end first lien 1-4 family residential mortgages with a remaining maturity or next repricing date of:)
                    'RCB-A555-itemM2b': row['RCONA555'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    'RCB-A556-itemM2b': row['RCONA556'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    'RCB-A557-itemM2b': row['RCONA557'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    'RCB-A558-itemM2b': row['RCONA558'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    'RCB-A559-itemM2b': row['RCONA559'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    # Over 15 years
                    'RCB-A560-itemM2b': row['RCONA560'] / RCB_itemM2b_entry1 if RCB_itemM2b_entry1 != 0 else 0,
                    #####---------Scheduel RC---------#####
                    ####----Group-specific Ratios----####
                    ###---Total assets
                    'RC-Item1-Item12': RC_item1_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    'RC-Item2-Item12': RC_item2_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    'RC-Item4-Item12': RC_item4_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    'RC-Item14-Item12': RC_item14_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    'RC-Item10-Item12': RC_item10_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    # 'RC-Item11-Item12': RC_item11_entry1 / RC_item12_entry1 if RC_item12_entry1 != 0 else 0,
                    ###---Total liabilities
                    'RC-Item4-Item21': RC_item4_entry1 / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    'RC-Item5-Item21': RC_item5_entry1 / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    'RC-2200-Item21': row['RCON2200'] / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    'RC-3548-Item21': row['RCON3548'] / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    'RC-3190-Item21': row['RCON3190'] / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    'RC-2930-Item21': row['RCON2930'] / RC_item21_entry1 if RC_item21_entry1 != 0 else 0,
                    ###---Total equity
                    'RC-Item10-G105': RC_item10_entry1 / row['RCONG105'] if row['RCONG105'] != 0 else 0,
                    #####---------Scheduel RC-E---------#####
                    ####----Deposit Ratios----####
                    ###---Transaction accounts
                    'RCE-B549-2215': row['RCONB549'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2202-2215': row['RCON2202'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2203-2215': row['RCON2203'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-B551-2215': row['RCONB551'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2213-2215': row['RCON2213'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2216-2215': row['RCON2216'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2215-2200': row['RCON2215'] / row['RCON2200'] if row['RCON2200'] != 0 else 0,
                    ###---Nontransaction accounts
                    'RCE-B550-2385': row['RCONB550'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-2385-2200': row['RCON2385'] / row['RCON2200'] if row['RCON2200'] != 0 else 0,
                    ##---Time Deposits
                    'RCE-itemM2a-2385': RCE_savings_entry1 / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-6648-2385': row['RCON6648'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-J473-2385': row['RCONJ473'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-J474-2385': row['RCONJ474'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    #---Time deposits < $250,000
                    #'RCE-HK07-savings': row['RCONHK07'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else ['RCONA579'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    #'RCE-HK08-savings': row['RCONHK08'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else ['RCONA580'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    #'RCE-HK09-savings': row['RCONHK09'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else ['RCONA581'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    #'RCE-HK10-savings': row['RCONHK10'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else ['RCONA582'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    'RCE-HK07-savings': row['RCONHK07'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else row['RCONA579'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    'RCE-HK08-savings': row['RCONHK08'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else row['RCONA580'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    'RCE-HK09-savings': row['RCONHK09'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else row['RCONA581'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    'RCE-HK10-savings': row['RCONHK10'] / RCE_time_depo_250K_entry1 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry1 != 0 else row['RCONA582'] / RCE_time_depo_250K_entry1 if RCE_time_depo_250K_entry1 != 0 else 0,
                    #####---------Scheduel RC-R Part I---------#####
                    ####----Risk-Weighted Assets----####
                    ###---Common Equity Tier 1 Ratio
                    # 'RCRI-P859-A223': row['RCOAP793'] if row['RCON9999'] >= 20150331 else row['RCOAP859'] / row['RCOAA223'] if row['RCOAA223'] != 0 else 0,
                    'RCRI-P840-A223': row['RCOAP840'] / row['RCOAA223'] if row['RCOAA223'] != 0 else 0,
                    'RCRI-P840-RWA+': row['RCOAP840'] / RWA_Basel_entry1 if RWA_Basel_entry1 != 0 else 0,
                    'RCRI-P859-A223': row['RCOAP859'] / row['RCOAA223'] if row['RCOAA223'] != 0 else 0,
                    'RCRI-P859-RWA+': row['RCOAP859'] / RWA_Basel_entry1 if RWA_Basel_entry1 != 0 else 0,
                    # 'RCRI-ZRWA-A223': row['RCOND987'] / row['RCOAA223'] if row['RCON9999'] >= 20150331 and row['RCOND987'] != 0 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0,
                    'RCRI-ZRWA-A223': row['RCOND987'] / row['RCOAA223'] if row['RCON9999'] >= 20150331 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0,
                    'RCRI-ZRWA-RWA': row['RCOND987'] / RWA_Basel_entry1 if row['RCON9999'] >= 20150331 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0,
                    'RCRI-ZRWA-RWA+': (row['RCOND987']-(ZRWA_Ratio_entry1*RWA_adjustment_entry1)) / RWA_Basel_entry1 if row['RCON9999'] >= 20150331 else row['RCONB696'] / row['RCOAA223'] if row['RCON9999'] < 20150311 else 0,
                    'RCRI-ZRWA-RWA++': 1 - RCRI_ZRWA_RWA4 / RCRI_ZRWA_RWA3 if RCRI_ZRWA_RWA3 != 0 else 0
                }
                entries_1_rcb.append(entry1)
                
                # --- Entry 2 Calculations ---
                # Common Variables
                call_id = row['IDRSSD']
                date_id = row['RCON9999']
                CERT = row['FDIC Certificate Number']

                #####-----Schedule RC-----#####
                ###---Cash
                RC_item1_entry2 = row['RCFD0081'] + row['RCFD0071']
                ###---Securities
                RC_item2_entry2 = (
                    row['RCFDJJ34'] + row['RCFD1773'] + row['RCFDJA22'] if row['RCON9999'] >= 20190331 else row['RCFD1754'] + row['RCFD1773']
                ) ##--HTM securities (from Schedule RC-B, column A [less Schedule RI-B Part II, Item 7, column B])
                ###---Loans and lease financing receivables (from Schedule RC-C)
                RC_item4_entry2 = row['RCFD5369'] + row['RCFDB529']
                ###---Trading assets (from Schedule RC-D)
                RC_item5_entry2 = row['RCFD3545']
                ###---Other real estate owned (from Schedule RC-M)
                RC_item7_entry2 = row['RCFD2150']
                ###---Intangible assets (from Schedule RC-M)
                RC_item10_entry2 = (
                    row['RCFD2143'] if row['RCON9999'] >= 20180630 else row['RCFD3163'] + row['RCFD0426']
                )
                ###---Total assets---###
                RC_item12_entry2 = (
                    row['RCFD2170'] - row['RCFDJA22'] + row['RCFD3123'] if row['RCON9999'] >= 20180331 else row['RCFD2170'] + row['RCFD3123']
                )
                ###---Total liabilities---###
                RC_item14_entry2 = row['RCONB993'] + row['RCFDB995']
                RC_item21_entry2 = row['RCFD2948'] + row['RCFD3123']
                ###---Total equity capital---###
                RC_item28_entry2 = (
                    row['RCFDG105'] - row['RCFDJA22'] if row['RCON9999'] >= 20180331 else row['RCFDG105']
                )
                #####-----Schedule RC-B-----#####
                ### Government Securities
                RCB_item2_htm_ac_entry2 = (
                    row['RCFDHT50'] if row['RCON9999'] > 20180331 else row['RCFD1289'] + row['RCFD1294']
                )
                RCB_item2_htm_fv_entry2 = (
                    row['RCFDHT51'] if row['RCON9999'] > 20180331 else row['RCFD1290'] + row['RCFD1295']
                )
                RCB_item2_afs_fv_entry2 = (
                    row['RCFDHT53'] if row['RCON9999'] > 20180331 else row['RCFD1293'] + row['RCFD1298']
                )
                
                # Mortgage-backed Securities - Item 4.a
                RCB_item4a_htm_ac_entry2 = row['RCFDG300'] + row['RCFDG304'] + row['RCFDG308']
                RCB_item4a_htm_fv_entry2 = row['RCFDG301'] + row['RCFDG305'] + row['RCFDG309']
                RCB_item4a_afs_fv_entry2 = row['RCFDG303'] + row['RCFDG307'] + row['RCFDG311']
                
                # Item 4.b
                RCB_item4b_htm_ac_entry2 = row['RCFDG312'] + row['RCFDG316'] + row['RCFDG320']
                RCB_item4b_htm_fv_entry2 = row['RCFDG313'] + row['RCFDG317'] + row['RCFDG321']
                RCB_item4b_afs_fv_entry2 = row['RCFDG315'] + row['RCFDG319'] + row['RCFDG323']
                
                ###---Item 4 - Total---###
                ##--Item 4.c--##
                # Item 4.c.1
                RCB_item4c1_htm_ac_entry2 = (
                    row['RCFDK142'] + row['RCFDK146'] if row['RCON9999'] > 20110331 else row['RCFDG324']
                )
                RCB_item4c1_htm_fv_entry2 = (
                    row['RCFDK143'] + row['RCFDK147'] if row['RCON9999'] > 20110331 else row['RCFDG325']
                )
                RCB_item4c1_afs_fv_entry2 = (
                    row['RCFDK145'] + row['RCFDK149'] if row['RCON9999'] > 20110331 else row['RCFDG327']
                )
                
                # Item 4.c.2
                RCB_item4c2_htm_ac_entry2 = (
                    row['RCFDK150'] + row['RCFDK154'] if row['RCON9999'] > 20110331 else row['RCFDG328']
                )
                RCB_item4c2_htm_fv_entry2 = (
                    row['RCFDK151'] + row['RCFDK155'] if row['RCON9999'] > 20110331 else row['RCFDG329']
                )
                RCB_item4c2_afs_fv_entry2 = (
                    row['RCFDK153'] + row['RCFDK157'] if row['RCON9999'] > 20110331 else row['RCFDG331']
                )

                # Item 4.c
                RCB_item4c_htm_ac_entry2 = RCB_item4c1_htm_ac_entry2 + RCB_item4c2_htm_ac_entry2
                RCB_item4c_htm_fv_entry2 = RCB_item4c1_htm_fv_entry2 + RCB_item4c2_htm_fv_entry2
                RCB_item4c_afs_fv_entry2 = RCB_item4c1_afs_fv_entry2 + RCB_item4c2_afs_fv_entry2
                
                # Item 4 - Total
                RCB_item4_htm_ac_entry2 = RCB_item4a_htm_ac_entry2 + RCB_item4b_htm_ac_entry2 + RCB_item4c_htm_ac_entry2
                ###---Memoranda Items
                # Item M.2.a - Total
                RCB_itemM2a_entry2 = row['RCFDA549'] + row['RCFDA550'] + row['RCFDA551'] + row['RCFDA552'] + row['RCFDA553'] + row['RCFDA554']
                RCB_itemM2b_entry2 = row['RCFDA555'] + row['RCFDA556'] + row['RCFDA557'] + row['RCFDA558'] + row['RCFDA559'] + row['RCFDA560']
                #####-----Schedule RC-E-----#####
                ###---Nontransaction accounts
                # Savings deposits
                RCE_savings_entry2 = row['RCON6810'] + row['RCON0352']
                RCE_time_depo_250K_entry2 = row['RCON6648'] + row['RCONJ473']
                #####-----Schedule RC-R Part I-----#####
                ###---Common Equity Tier 1 Capital
                RCB_item4c2_htm_ac_xyzentry2 = (
                    row['RCFAP859'] + row['RCFAP858'] if row['RCON9999'] >= 20200331 and row['RCFAP859'] != '' else row['RCFAP859'] + row['RCFAP858']
                )
                RCB_item4c2_htm_fv_abcentry2 = (
                    row['RCFAP859'] + row['RCFAP858'] if row['RCON9999'] >= 20200331 and row['RCFAP859'] != '' else row['RCFAP859'] + row['RCFAP858']
                )
                RCRI_CET1_Basel_entry2 = row['RCFAP793']
                ###---Risk-Weighted Assets
                RWA_Basel_entry2 = row['RCFAA223'] + (0.15*row['RCFDA554'] + 0.1*row['RCFDA553'] + 0.08*row['RCFDA552'] + 0.15*row['RCFDA560'] + 0.1*row['RCFDA559'] + 0.08*row['RCFDA558'])
                # RWA_adjustment_entry2 = (row['RCFDA554'] + row['RCFDA553'] + row['RCFDA552'] + row['RCFDA560'] + row['RCFDA559'] + row['RCFDA558'])
                RWA_adjustment_entry2 = (row['RCFDA554'] + row['RCFDA553'] + row['RCFDA560'] + row['RCFDA559'])
                ###---ZRWA
                ZRWA_Ratio_entry2 = (row['RCOND962']+row['RCOND967'])/(row['RCON1754']+row['RCON1773']) if row['RCON9999'] >= 20150331 and (row['RCON1754']+row['RCON1773']) != 0 else (row['RCOND962']+row['RCOND967'])/(row['RCFD1754']+row['RCFD1773']) if row['RCON9999'] >= 20150331 and (row['RCFD1754']+row['RCFD1773']) != 0 else (row['RCONB603']+row['RCONB608'])/(row['RCON1754']+row['RCON1773']) if row['RCON9999'] < 20150331 and row['RCON1754']+row['RCON1773'] != 0 else 0
                RCRI_ZRWA_RWA = row['RCOND987'] / RWA_Basel_entry2 if row['RCON9999'] >= 20150331 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0
                RCRI_ZRWA_RWA2 = (row['RCOND987']-(ZRWA_Ratio_entry2*RWA_adjustment_entry2)) / RWA_Basel_entry2 if row['RCON9999'] >= 20150331 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0
                
                entry2 = {
                    'IDRSSD': call_id,
                    'RCON9999': date_id,
                    'CERT': CERT,
                    #####---------Scheduel RC-B---------#####
                    ####----Group-specific Ratios----####
                    ###---U.S Treasury securities
                    'RCB-0211-1754': row['RCFD0211'] / row['RCFD1754'] if row['RCFD1754'] != 0 else 0,
                    'RCB-1287-1773': row['RCFD1287'] / row['RCFD1773'] if row['RCFD1773'] != 0 else 0,
                    'RCB-item4-1754': RCB_item4_htm_ac_entry2 / row['RCFD1754'] if row['RCFD1754'] != 0 else 0,
                    ###---U.S. Government agency and sponsored agency obligations
                    'RCB-HT50-1754': RCB_item2_htm_ac_entry2 / row['RCFD1754'] if row['RCFD1754'] != 0 else 0,
                    'RCB-HT53-1773': RCB_item2_afs_fv_entry2 / row['RCFD1773'] if row['RCFD1773'] != 0 else 0,
                    ###---Securities issued by states and political subdivisions
                    'RCB-8496-1754': row['RCFD8496'] / row['RCFD1754'] if row['RCFD1754'] != 0 else 0,
                    'RCB-8499-1773': row['RCFD8499'] / row['RCFD1773'] if row['RCFD1773'] != 0 else 0,
                    ###---Mortgage-backed securities
                    ##--Residential mortgage pass-through securities
                    'RCB-G300-item4a': row['RCFDG300'] / RCB_item4a_htm_ac_entry2 if RCB_item4a_htm_ac_entry2 != 0 else 0,
                    'RCB-G304-item4a': row['RCFDG304'] / RCB_item4a_htm_ac_entry2 if RCB_item4a_htm_ac_entry2 != 0 else 0,
                    'RCB-G308-item4a': row['RCFDG308'] / RCB_item4a_htm_ac_entry2 if RCB_item4a_htm_ac_entry2 != 0 else 0,
                    'RCB-G303-item4a': row['RCFDG303'] / RCB_item4a_afs_fv_entry2 if RCB_item4a_afs_fv_entry2 != 0 else 0,
                    'RCB-G307-item4a': row['RCFDG307'] / RCB_item4a_afs_fv_entry2 if RCB_item4a_afs_fv_entry2 != 0 else 0,
                    'RCB-G311-item4a': row['RCFDG311'] / RCB_item4a_afs_fv_entry2 if RCB_item4a_afs_fv_entry2 != 0 else 0,
                    ##--Other residential mortgage-backed securities
                    'RCB-G312-item4b': row['RCFDG312'] / RCB_item4b_htm_ac_entry2 if RCB_item4b_htm_ac_entry2 != 0 else 0,
                    'RCB-G316-Item4b': row['RCFDG316'] / RCB_item4b_htm_ac_entry2 if RCB_item4b_htm_ac_entry2 != 0 else 0,
                    'RCB-G320-Item4b': row['RCFDG320'] / RCB_item4b_htm_ac_entry2 if RCB_item4b_htm_ac_entry2 != 0 else 0,
                    'RCB-G315-item4b': row['RCFDG315'] / RCB_item4b_afs_fv_entry2 if RCB_item4b_afs_fv_entry2 != 0 else 0,
                    'RCB-G319-Item4b': row['RCFDG319'] / RCB_item4b_afs_fv_entry2 if RCB_item4b_afs_fv_entry2 != 0 else 0,
                    'RCB-G323-Item4b': row['RCFDG323'] / RCB_item4b_afs_fv_entry2 if RCB_item4b_afs_fv_entry2 != 0 else 0,
                    ##--Commercial mortgage-backed securities
                    #-Commercial mortgage pass-through securities
                    'RCB-Item4c1-Item4c': RCB_item4c1_htm_ac_entry2 / RCB_item4c_htm_ac_entry2 if RCB_item4c_htm_ac_entry2 != 0 else 0,
                    #-Other commercial MBS
                    'RCB-Item4c2-Item4c': RCB_item4c2_htm_ac_entry2 / RCB_item4c_htm_ac_entry2 if RCB_item4c_htm_ac_entry2 != 0 else 0,
                    #####-----Domain-specific Ratios-----#####
                    'RCB-0213-0111': row['RCFD0211'] / row['RCFD1754'] if row['RCFD1754'] != 0 else 0,
                    'RCB-HT51-HT50': RCB_item2_htm_fv_entry2 / RCB_item2_htm_ac_entry2 if RCB_item2_htm_ac_entry2 != 0 else 0,
                    'RCB-8497-8496': row['RCFD8497'] / row['RCFD8496'] if row['RCFD8496'] != 0 else 0,
                    'RCB-item4a-fv2ac': RCB_item4a_htm_fv_entry2 / RCB_item4a_htm_ac_entry2 if RCB_item4a_htm_ac_entry2 != 0 else 0,
                    'RCB-item4b-fv2ac': RCB_item4b_htm_fv_entry2 / RCB_item4b_htm_ac_entry2 if RCB_item4b_htm_ac_entry2 != 0 else 0,
                    'RCB-item4c-fv2ac': RCB_item4c_htm_fv_entry2 / RCB_item4c_htm_ac_entry2 if RCB_item4c_htm_ac_entry2 != 0 else 0,
                    ###---Item M.2.a (securities issued by the U.S. Treasury, U.S. Governmental agencies and states and plitical subdivisions in the U.S with a remaining maturity or next repricing date of:)
                    'RCB-A549-itemM2a': row['RCFDA549'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    'RCB-A550-itemM2a': row['RCFDA550'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    'RCB-A551-itemM2a': row['RCFDA551'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    'RCB-A552-itemM2a': row['RCFDA552'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    'RCB-A553-itemM2a': row['RCFDA553'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    # Over 15 years
                    'RCB-A554-itemM2a': row['RCFDA554'] / RCB_itemM2a_entry2 if RCB_itemM2a_entry2 != 0 else 0,
                    ###---Item M.2.b (Mortgage pass-through securities backed by closed-end first lien 1-4 family residential mortgages with a remaining maturity or next repricing date of:)
                    'RCB-A555-itemM2b': row['RCFDA555'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    'RCB-A556-itemM2b': row['RCFDA556'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    'RCB-A557-itemM2b': row['RCFDA557'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    'RCB-A558-itemM2b': row['RCFDA558'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    'RCB-A559-itemM2b': row['RCFDA559'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    # Over 15 years
                    'RCB-A560-itemM2b': row['RCFDA560'] / RCB_itemM2b_entry2 if RCB_itemM2b_entry2 != 0 else 0,
                    #####---------Scheduel RC---------#####
                    ####----Group-specific Ratios----####
                    ###---Total assets
                    'RC-Item1-Item12': RC_item1_entry2 / RC_item12_entry2 if RC_item12_entry2 != 0 else 0,
                    'RC-Item2-Item12': RC_item2_entry2 / RC_item12_entry2 if RC_item12_entry2 != 0 else 0,
                    'RC-Item4-Item12': RC_item4_entry2 / RC_item12_entry2 if RC_item12_entry2 != 0 else 0,
                    'RC-Item14-Item12': RC_item14_entry2 / RC_item12_entry2 if RC_item12_entry2 != 0 else 0,
                    ###---Total liabilities
                    'RC-Item4-Item21': RC_item4_entry2 / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    'RC-Item5-Item21': RC_item5_entry2 / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    'RC-2200-Item21': row['RCON2200'] / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    'RC-3548-Item21': row['RCFD3548'] / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    'RC-3190-Item21': row['RCFD3190'] / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    'RC-2930-Item21': row['RCFD2930'] / RC_item21_entry2 if RC_item21_entry2 != 0 else 0,
                    ###---Total equity
                    'RC-Item10-G105': RC_item10_entry2 / row['RCFDG105'] if row['RCFDG105'] != 0 else 0,
                    #####---------Scheduel RC-E---------#####
                    ####----Deposit Ratios----####
                    ###---Transaction accounts
                    'RCE-B549-2215': row['RCONB549'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2202-2215': row['RCON2202'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2203-2215': row['RCON2203'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-B551-2215': row['RCONB551'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2213-2215': row['RCON2213'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2216-2215': row['RCON2216'] / row['RCON2215'] if row['RCON2215'] != 0 else 0,
                    'RCE-2215-2200': row['RCON2215'] / row['RCON2200'] if row['RCON2200'] != 0 else 0,
                    ###---Nontransaction accounts
                    'RCE-B550-2385': row['RCONB550'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-2385-2200': row['RCON2385'] / row['RCON2200'] if row['RCON2200'] != 0 else 0,
                    ##---Time Deposits
                    'RCE-itemM2a-2385': RCE_savings_entry2 / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-6648-2385': row['RCON6648'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-J473-2385': row['RCONJ473'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    'RCE-J474-2385': row['RCONJ474'] / row['RCON2385'] if row['RCON2385'] != 0 else 0,
                    #---Time deposits < $250,000
                    #'RCE-HK07-savings': row['RCONHK07'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else ['RCONA579'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    #'RCE-HK08-savings': row['RCONHK08'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else ['RCONA580'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    #'RCE-HK09-savings': row['RCONHK09'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else ['RCONA581'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    #'RCE-HK10-savings': row['RCONHK10'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else ['RCONA582'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    'RCE-HK07-savings': row['RCONHK07'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else row['RCONA579'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    'RCE-HK08-savings': row['RCONHK08'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else row['RCONA580'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    'RCE-HK09-savings': row['RCONHK09'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else row['RCONA581'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    'RCE-HK10-savings': row['RCONHK10'] / RCE_time_depo_250K_entry2 if row['RCON9999'] >= 20170331 and RCE_time_depo_250K_entry2 != 0 else row['RCONA582'] / RCE_time_depo_250K_entry2 if RCE_time_depo_250K_entry2 != 0 else 0,
                    #####---------Scheduel RC-R Part I---------#####
                    ####----Risk-Weighted Assets----####
                    ###---Common Equity Tier 1 Ratio
                    # 'RCRI-P859-A223': row['RCFAP793'] if row['RCON9999'] >= 20150331 else row['RCFAP859'] / row['RCFAA223'] if row['RCFAA223'] != 0 else 0,
                    'RCRI-P840-A223': row['RCFAP840'] / row['RCFAA223'] if row['RCFAA223'] != 0 else 0,
                    'RCRI-P840-RWA+': row['RCFAP840'] / RWA_Basel_entry2 if RWA_Basel_entry2 != 0 else 0,
                    'RCRI-P859-A223': row['RCFAP859'] / row['RCFAA223'] if row['RCFAA223'] != 0 else 0,
                    'RCRI-P859-RWA+': row['RCFAP859'] / RWA_Basel_entry2 if RWA_Basel_entry2 != 0 else 0,
                    # 'RCRI-ZRWA-A223': row['RCOND987'] / row['RCFAA223'] if row['RCOND987'] != 0 else row['RCFDD987'] / row['RCFAA223'] if row['RCFDD987'] != 0 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0,
                    'RCRI-ZRWA-A223': row['RCOND987'] / row['RCFAA223'] if row['RCON9999'] >= 20150331 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0,
                    'RCRI-ZRWA-RWA': row['RCOND987'] / RWA_Basel_entry2 if row['RCON9999'] >= 20150331 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0,
                    'RCRI-ZRWA-RWA+': (row['RCOND987']-(ZRWA_Ratio_entry2*RWA_adjustment_entry2)) / RWA_Basel_entry2 if row['RCON9999'] >= 20150331 else row['RCFDB696'] / row['RCFAA223'] if row['RCON9999'] < 20150331 else 0,
                    'RCRI-ZRWA-RWA++': 1 - RCRI_ZRWA_RWA2 / RCRI_ZRWA_RWA if RCRI_ZRWA_RWA != 0 else 0

                }
                entries_2_rcb.append(entry2)
            
            # Create DataFrames
            df_entry1_rcb = pd.DataFrame(entries_1_rcb)
            df_entry2_rcb = pd.DataFrame(entries_2_rcb)
            
            # Interleave Rows
            interleaved_rows_rcb = [row for pair in zip(df_entry1_rcb.values, df_entry2_rcb.values) for row in pair]
            interleaved_df_rcb = pd.DataFrame(interleaved_rows_rcb, columns=df_entry1_rcb.columns)
            
            # Cleaning: Remove rows where the fourth column is empty
            interleaved_df_rcb = interleaved_df_rcb[interleaved_df_rcb.iloc[:, 7].notna()]

            # Remove duplicate IDRSSDs based on blank cells
            interleaved_df_rcb['blank_cells'] = interleaved_df_rcb.isnull().sum(axis=1)  # Count blank cells
            interleaved_df_rcb = interleaved_df_rcb.sort_values(by=['IDRSSD', 'blank_cells'], ascending=[True, True])
            interleaved_df_rcb = interleaved_df_rcb.drop_duplicates(subset='IDRSSD', keep='first')
            interleaved_df_rcb = interleaved_df_rcb.drop(columns=['blank_cells'])  # Drop helper column
            
            # Save the cleaned DataFrame to CSV
            output_file_path = os.path.join(interleaved_directory, file_name)
            interleaved_df_rcb.to_csv(output_file_path, index=False)
            print(f"Processed and saved: {output_file_path}")
        
        except Exception as e:
            print(f"Error processing file {file_name}: {e}")

print("All files in '/Cleaned' have been processed and saved to '/Interleaved'.")
