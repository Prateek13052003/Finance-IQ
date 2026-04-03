from finance.crew import ResearchCrew
import os

os.makedirs('output', exist_ok=True)

def run():
    company = input("Enter company name: ")

    inputs = {
        'company': company
    }

    result = ResearchCrew().crew().kickoff(inputs=inputs)

    print("\n\n=== FINAL REPORT ===\n\n")
    print(result.raw)

    if "No reliable data available" in result.raw:
        print("⚠️ Warning: Insufficient real data found")

    if not result.raw or len(result.raw) < 50:
        print("⚠️ Output seems incomplete or unreliable")

    print("\n\nReport has been saved to output/report.md")

if __name__ == "__main__":
    run()