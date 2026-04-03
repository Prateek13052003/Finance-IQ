"""
crew.py — ResearchCrew with live callback support.

The Streamlit app (app.py) patches step_callback / task_callback onto
the Crew object after creation, so this file stays clean and unmodified
from standard CrewAI structure. No changes needed here — but comments
have been added for clarity.
"""

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

# ── LLM & Tools ───────────────────────────────────────────────────────────────
llm         = LLM(model="groq/llama-3.3-70b-versatile")
search_tool = SerperDevTool()


@CrewBase
class ResearchCrew:
    """
    Two-agent financial research crew.

    Agents:
      • researcher  — searches the web and gathers verified facts
      • analyst     — structures the research into a professional report

    Usage from Streamlit (app.py):
        crew_inst    = ResearchCrew()
        crew_obj     = crew_inst.crew()          # get the Crew object
        crew_obj.step_callback = my_step_fn      # inject live callbacks
        crew_obj.task_callback = my_task_fn
        result       = crew_obj.kickoff(inputs={"company": company})
    """

    # ── Agents ────────────────────────────────────────────────────────────────

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            verbose=True,
            tools=[search_tool],
            llm=llm,
            allow_delegation=False,
            max_iter=3,
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["analyst"],
            verbose=True,
            llm=llm,
            allow_delegation=False,
            max_iter=3,
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["analysis_task"],
            output_file="output/report.md",
        )

    # ── Crew ──────────────────────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """
        Returns the assembled Crew.

        step_callback and task_callback are left as None here;
        app.py injects them after calling this method so that
        Streamlit can receive live log updates without coupling
        the crew logic to any specific UI framework.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            # Callbacks are patched in by app.py at runtime:
            #   crew_obj.step_callback = ...
            #   crew_obj.task_callback = ...
        )