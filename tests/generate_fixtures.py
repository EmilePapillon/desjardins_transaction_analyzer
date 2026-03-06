#!/usr/bin/env python3
"""
Generate synthetic bank statement PDFs for use as test fixtures.
All names, addresses, account numbers, and transaction data are entirely fictional.
Run once: python tests/generate_fixtures.py
"""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

SUPPORT_DIR = os.path.join(os.path.dirname(__file__), "support")
PAGE_W, PAGE_H = letter  # 612 x 792 points


def rl_y(pdfplumber_top: float) -> float:
    """Convert pdfplumber top-from-top coordinate to reportlab bottom-from-bottom."""
    return PAGE_H - pdfplumber_top


def generate_desjardins():
    """
    Synthetic Desjardins Odyssée Mastercard statement.
    The parser needs: 'DESJARDINS' + 'DATE DU RELE' + 'Année YYYY' in text,
    and transaction lines matching: DD MM DD MM DESCRIPTION [percent%] amount
    """
    path = os.path.join(SUPPORT_DIR, "06-############3000-juin-2025.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica", 10)

    lines = [
        # Branding / header (triggers can_parse)
        (69, 60, "DESJARDINS ODYSSEE WORLDELITE MASTERCARD"),
        (69, 80, "DATE DU RELEVE DE COMPTE"),
        (69, 95, "Année 2025"),
        (69, 110, "JANE DOE"),
        (69, 125, "123 MAIN ST, SAMPLETOWN ON A1B 2C3"),
        # Column headers
        (69, 160, "Date         Date de        Description                              Montant"),
        (69, 175, "opération    comptabilisation"),
        # Transactions: format = "DD MM DD MM DESCRIPTION [X,XX %] amount"
        (69, 200, "03 06 04 06 SAMPLE GROCERY STORE SAMPLETOWN ON 3,00 % 45,67"),
        (69, 215, "08 06 09 06 FICTIONAL HARDWARE CO 1,00 % 78,90"),
        (69, 230, "12 06 13 06 SAMPLE RESTAURANT 3,00 % 32,00"),
        (69, 245, "15 06 16 06 SAMPLE GAS STATION 1,00 % 55,00"),
        (69, 260, "20 06 21 06 PAIEMENT CAISSE 1,00 % 211,57CR"),
    ]

    for x, top, text in lines:
        c.drawString(x, rl_y(top), text)

    c.save()
    print(f"  Written: {path}")


def generate_td():
    """
    Synthetic TD Minimum Chequing statement.
    The TD parser uses extract_words() + x-coordinates to distinguish
    Withdrawals (x0 ~228-305) from Deposits (x0 ~339-404).
    Column layout mirrors the real TD statement format exactly.
    """
    path = os.path.join(
        SUPPORT_DIR,
        "TD_MINIMUM_CHEQUING_ACCOUNT_3880-6614931_Oct_31-Nov_28_2025.pdf",
    )
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica", 10)

    def text(x_pt, top_pt, s, align="left"):
        y = rl_y(top_pt)
        if align == "right":
            c.drawRightString(x_pt, y, s)
        else:
            c.drawString(x_pt, y, s)

    # --- Branding / header (triggers can_parse) ---
    text(69, 40, "ACCOUNTISSUEDBY:THETORONTO-DOMINIONBANK")
    text(69, 55, "Statement ofAccount")
    text(69, 70, "BRANCHNO.")
    text(69, 85, "JANE DOE")
    text(69, 100, "123 MAIN ST, SAMPLETOWN ON A1B 2C3")

    # Date range (triggers parse_date_range)
    text(426, 115, "OCT31/25-NOV28/25")

    # Branch / account (fictional)
    text(93, 130, "9999")
    text(153, 130, "0000-0000000")

    # --- Column headers (x positions must match real layout) ---
    text(108, 160, "Description")
    text(228, 160, "Withdrawals")
    text(339, 160, "Deposits")
    text(419, 160, "Date")
    text(480, 160, "Balance")

    # --- Starting balance ---
    text(69, 175, "STARTINGBALANCE")
    text(416, 175, "OCT31")
    text(533, 175, "10,000.00", align="right")

    # Withdrawal row: amount in Withdrawals column (x0 ~279, right-edge ~305)
    text(69, 190, "SAMPLE-WITHDRAWAL")
    text(305, 190, "250.00", align="right")
    text(416, 190, "NOV03")
    text(533, 190, "9,750.00", align="right")

    # Another withdrawal row
    text(69, 205, "UTILITY-BILL-SAMPLE")
    text(305, 205, "120.00", align="right")
    text(416, 205, "NOV14")

    # Another withdrawal
    text(69, 220, "SAMPLE-INSURANCE")
    text(305, 220, "80.00", align="right")
    text(416, 220, "NOV14")
    text(533, 220, "9,550.00", align="right")

    # Deposit row: amount in Deposits column (x0 ~378, right-edge ~404)
    text(69, 235, "SAMPLE-DEPOSIT")
    text(404, 235, "500.00", align="right")
    text(416, 235, "NOV20")
    text(533, 235, "10,050.00", align="right")

    # Monthly fee withdrawal
    text(69, 250, "MONTHLYACCOUNTFEE")
    text(305, 250, "3.95", align="right")
    text(416, 250, "NOV28")
    text(533, 250, "10,046.05", align="right")

    # Closing balance
    text(69, 265, "CLOSINGBALANCE")
    text(416, 265, "NOV28")
    text(533, 265, "10,046.05", align="right")

    c.save()
    print(f"  Written: {path}")


def generate_desjardins_jan():
    """
    Second synthetic Desjardins statement (janvier / December transactions).
    """
    path = os.path.join(SUPPORT_DIR, "11-############3000-janvier-2025.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica", 10)

    lines = [
        (69, 60, "DESJARDINS ODYSSEE WORLDELITE MASTERCARD"),
        (69, 80, "DATE DU RELEVE DE COMPTE"),
        (69, 95, "Année 2025"),
        (69, 110, "JANE DOE"),
        (69, 125, "123 MAIN ST, SAMPLETOWN ON A1B 2C3"),
        (69, 160, "Date         Date de        Description                              Montant"),
        (69, 175, "opération    comptabilisation"),
        (69, 200, "05 12 06 12 FICTIONAL GROCERY SAMPLETOWN ON 3,00 % 89,10"),
        (69, 215, "10 12 11 12 SAMPLE DEPT STORE 1,00 % 42,30"),
        (69, 230, "15 12 16 12 SAMPLE PHARMACY 1,00 % 18,50"),
        (69, 245, "20 12 21 12 PAIEMENT CAISSE 1,00 % 149,90CR"),
    ]

    for x, top, text in lines:
        c.drawString(x, rl_y(top), text)

    c.save()
    print(f"  Written: {path}")


if __name__ == "__main__":
    os.makedirs(SUPPORT_DIR, exist_ok=True)
    print("Generating synthetic test fixture PDFs...")
    generate_desjardins()
    generate_desjardins_jan()
    generate_td()
    print("Done.")
