"""Offline presentation contracts; no providers, rendering or persistence."""
import ast
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
import unittest
from unittest.mock import patch

from src import ui_contracts as ui
from src.models import SpecialistAnalysis, InterpretationStatement, ForecastStatement


class UIContractTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_navigation(self):
        self.assertEqual([p.key for p in ui.DASHBOARD_PAGES],
                         ['home', 'research', 'portfolio', 'agent_room', 'decision_history', 'performance'])
        with self.assertRaises(FrozenInstanceError): ui.DASHBOARD_PAGES[0].title = 'changed'
        with self.assertRaises(ValueError): ui.DashboardPage('', 'Title')

    def test_research_references_backend(self):
        from test_v01 import evidence, payload
        from src.analysis import _validate_analysis
        from src.evidence import build_evidence_catalog
        data = evidence()
        analysis = _validate_analysis(payload(data), data)
        catalog = build_evidence_catalog(data)
        page = ui.ResearchPageData(analysis=analysis, evidence_package=data, evidence_catalog=catalog)
        self.assertIs(page.analysis, analysis)
        self.assertIs(page.evidence_package, data)
        self.assertIs(page.evidence_catalog, catalog)
        self.assertNotIn('recommendation', {f.name for f in fields(page)})

    def test_portfolio_and_home(self):
        from src.models import PortfolioInput
        from src.portfolio_calculations import build_portfolio_snapshot
        from src.portfolio_risk import assess_portfolio_risk
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        risk = assess_portfolio_risk(snapshot)
        page = ui.PortfolioPageData(snapshot=snapshot, risk_assessment=risk)
        home = ui.HomePageData(portfolio=snapshot, risk_assessment=risk)
        self.assertIs(page.snapshot, snapshot)
        self.assertIs(home.portfolio, snapshot)
        self.assertIs(page.risk_assessment, risk)

    def test_agent_room_extensible_order(self):
        names = ('risk', 'future_test_specialist', 'fundamental')
        items = [SpecialistAnalysis(n, 'TEST', 'Summary', [InterpretationStatement('Finding', ['E001'])],
                                    [], [ForecastStatement('Scenario', ['E001'])], 60, []) for n in names]
        page = ui.AgentRoomPageData(registered_specialists=names, specialist_results=items)
        self.assertIs(page.specialist_results, items)
        self.assertEqual(tuple(x.specialist_name for x in page.specialist_results), names)
        self.assertFalse(any(f.name in ('fundamental_result', 'risk_result') for f in fields(page)))

    def test_history_keeps_original_types(self):
        from test_v03 import record, outcome
        from src.models import DecisionMemoryContext
        decision, later = record(), outcome()
        memory = DecisionMemoryContext('TEST', [])
        page = ui.DecisionHistoryPageData([decision], [later], memory)
        self.assertIs(page.decisions[0], decision)
        self.assertIs(page.outcomes[0], later)
        self.assertEqual(later.decision_id, decision.decision_id)
        self.assertIs(page.memory_context, memory)
        self.assertFalse(hasattr(decision, 'stock_return'))

    def test_availability(self):
        unsupported = ui.UISectionAvailability(False, False, 'Not archived')
        absent = ui.UISectionAvailability(True, False, 'No run yet')
        page = ui.ResearchPageData(availability={'analysis': absent, 'archive': unsupported})
        self.assertFalse(page.availability['archive'].backend_supported)
        self.assertIsNone(page.analysis)
        with self.assertRaises(ValueError): ui.UISectionAvailability(False, True)
        with self.assertRaises(ValueError): ui.UISectionAvailability(True, False, ' ')

    def test_performance_honest_default(self):
        page = ui.PerformancePageData()
        self.assertFalse(page.availability.backend_supported)
        self.assertFalse(page.availability.data_available)
        self.assertTrue(page.availability.reason)
        self.assertEqual([f.name for f in fields(page)], ['availability'])

    def test_empty_containers_independent(self):
        a, b = ui.AgentRoomPageData(), ui.AgentRoomPageData()
        a.availability['status'] = ui.UISectionAvailability(False, False, 'No event stream')
        self.assertEqual(b.availability, {})
        self.assertIsNot(a.specialist_results, b.specialist_results)

    def test_presentation_only_module(self):
        tree = ast.parse(Path(ui.__file__).read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(imports, ['dataclasses', 'src.models'])
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        self.assertTrue(all(isinstance(node.op, ast.BitOr) for node in ast.walk(tree) if isinstance(node, ast.BinOp)))
        functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.assertEqual(functions, ['__post_init__', '__post_init__'])


class DashboardShellTests(unittest.TestCase):
    def test_navigation_renders_all_pages_offline(self):
        from streamlit.testing.v1 import AppTest
        root = Path(__file__).resolve().parents[1]
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
            app = AppTest.from_file(str(root / 'dashboard.py')).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.sidebar.radio[0].options), 6)
            for key, title in [('home', 'Home'), ('research', 'Research'), ('portfolio', 'Portfolio'),
                               ('agent_room', 'Agent Room'), ('decision_history', 'Decision History'), ('performance', 'Performance')]:
                app.sidebar.radio[0].set_value(key).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.title[0].value, title)
                self.assertFalse(app.metric)
            self.assertIn('not implemented', app.info[0].value)

    def test_page_modules_import_and_boundaries(self):
        import importlib
        for page in ui.DASHBOARD_PAGES:
            module = importlib.import_module(f'src.dashboard.{page.key}')
            self.assertTrue(callable(module.render))
            tree = ast.parse(Path(module.__file__).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, ('src.ui_contracts', 'src.dashboard.components'))
                if isinstance(node, ast.Import):
                    self.assertEqual([alias.name for alias in node.names], ['streamlit'])
                self.assertNotIsInstance(node, ast.BinOp)

    def test_home_and_research_reserved_sections(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        self.assertEqual(len(app.subheader), 6)
        app.sidebar.radio[0].set_value('research').run()
        self.assertIn('Evidence / provenance', [x.value for x in app.subheader])
        self.assertFalse(app.button)
