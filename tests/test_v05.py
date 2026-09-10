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
    def setUp(self):
        bootstrap = patch('src.configuration.load_local_environment')
        bootstrap.start()
        self.addCleanup(bootstrap.stop)

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
                    self.assertIn(node.module, ('src.ui_contracts', 'src.dashboard.components', 'src.models', 'src.dashboard.research_adapter', 'src.dashboard.portfolio_adapter'))
                if isinstance(node, ast.Import):
                    self.assertEqual([alias.name for alias in node.names], ['streamlit'])


    def test_home_and_research_reserved_sections(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        self.assertEqual(len(app.subheader), 6)
        app.sidebar.radio[0].set_value('research').run()
        self.assertIn('Evidence / provenance', [x.value for x in app.subheader])
        self.assertEqual(app.button[0].label, 'Run Research')


class ResearchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        bootstrap = patch('src.configuration.load_local_environment')
        bootstrap.start()
        self.addCleanup(bootstrap.stop)
        from test_v01 import evidence, payload
        from src.analysis import _validate_analysis
        self.analysis = _validate_analysis(payload(evidence()), evidence())
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_normalization_and_invalid_input(self):
        from src.dashboard.research_adapter import normalize_ticker, run_research, ResearchInputError
        self.assertEqual(normalize_ticker(' aapl '), 'AAPL')
        with patch('src.dashboard.research_adapter.run_stock_research') as pipeline:
            for value in ('', '  ', 'A A', 'A<script>', '../', None):
                with self.assertRaises(ResearchInputError): run_research(value)
            pipeline.assert_not_called()

    def test_adapter_exact_pipeline_and_objects(self):
        from src.dashboard.research_adapter import run_research
        with patch('src.dashboard.research_adapter.run_stock_research', return_value=self.analysis) as pipeline:
            data = run_research(' test ')
        pipeline.assert_called_once_with('TEST', use_multi_agent=True, persist_decision=False, use_decision_memory=False)
        self.assertIs(data.analysis, self.analysis)
        self.assertIs(data.analysis.bull_case, self.analysis.bull_case)
        self.assertIsNone(data.evidence_catalog)
        self.assertFalse(data.availability['specialists'].data_available)

    def test_safe_failure(self):
        from src.dashboard.research_adapter import run_research, ResearchRunError
        with patch('src.dashboard.research_adapter.run_stock_research', side_effect=RuntimeError('secret-test-value')):
            with self.assertRaises(ResearchRunError) as caught: run_research('TEST')
        self.assertNotIn('secret-test-value', str(caught.exception))

    def test_submission_rerun_navigation_and_failed_new_run(self):
        from streamlit.testing.v1 import AppTest
        from src.dashboard.research_adapter import run_research
        with patch('src.dashboard.research_adapter.run_stock_research', return_value=self.analysis) as pipeline:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
            app.sidebar.radio[0].set_value('research').run()
            app.text_input[0].set_value('TEST').run()
            pipeline.assert_not_called()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            pipeline.assert_called_once()
            self.assertEqual(app.metric[0].value, self.analysis.recommendation)
            app.run()
            app.sidebar.radio[0].set_value('home').run()
            app.sidebar.radio[0].set_value('research').run()
            pipeline.assert_called_once()
            self.assertTrue(any('FORECAST' == x.value for x in app.caption))
            self.assertTrue(any('AI INTERPRETATION' == x.value for x in app.caption))
            pipeline.side_effect = RuntimeError('secret-test-value')
            app.text_input[0].set_value('OTHER')
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)
            self.assertTrue(app.error)
            self.assertNotIn('secret-test-value', app.error[0].value)

    def test_generic_specialist_renderer(self):
        from streamlit.testing.v1 import AppTest
        script = '''
from src.dashboard.research import specialist_results
from src.models import SpecialistAnalysis
specialist_results([SpecialistAnalysis(n, 'TEST', 'Summary', [], [], [], 60, [])
                    for n in ('risk', 'future_test_specialist', 'fundamental')])
'''
        app = AppTest.from_string(script).run()
        self.assertFalse(app.exception)
        self.assertEqual([x.value for x in app.subheader], ['risk', 'future_test_specialist', 'fundamental'])

    def test_adapter_import_boundary(self):
        import src.dashboard.research_adapter as adapter
        tree = ast.parse(Path(adapter.__file__).read_text())
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertEqual(modules, ['src.research_pipeline', 'src.ui_contracts'])


    def test_execution_controls_visible_with_retained_result(self):
        from streamlit.testing.v1 import AppTest
        from src.dashboard.research_adapter import run_research
        with patch('src.dashboard.research_adapter.run_stock_research', return_value=self.analysis) as pipeline:
            retained = run_research('TEST')
            pipeline.reset_mock()
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py'))
            app.session_state['research_result'] = retained
            app.run()
            app.sidebar.radio[0].set_value('research').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input[0].label, 'Ticker')
            self.assertEqual(app.button[0].label, 'Run Research')
            self.assertEqual(app.subheader[0].value, 'Run company research')
            self.assertEqual(app.metric[0].value, self.analysis.recommendation)
            pipeline.assert_not_called()
            app.text_input[0].set_value(' test ').run()
            pipeline.assert_not_called()
            app.button[0].click().run()
            pipeline.assert_called_once_with('TEST', use_multi_agent=True, persist_decision=False, use_decision_memory=False)
            app.run()
            pipeline.assert_called_once()
            self.assertEqual(app.text_input[0].label, 'Ticker')
            self.assertEqual(app.button[0].label, 'Run Research')


class ResearchDiagnosticTests(unittest.TestCase):
    def test_safe_internal_log_and_ui_error(self):
        from src.dashboard.research_adapter import run_research, ResearchRunError
        with patch('src.dashboard.research_adapter.run_stock_research', side_effect=RuntimeError('OpenAI connection failed or timed out.')) as pipeline:
            with self.assertLogs('src.dashboard.research_adapter', level='ERROR') as logs:
                with self.assertRaises(ResearchRunError) as caught:
                    run_research('AAPL')
            pipeline.assert_called_once()
        self.assertIn('exception=RuntimeError', logs.output[0])
        self.assertIn('OpenAI connection failed or timed out.', logs.output[0])
        self.assertNotIn('OpenAI connection', str(caught.exception))

    def test_secret_and_payload_withheld(self):
        from src.dashboard.research_adapter import run_research, ResearchRunError
        secret = 'private-fixture-key'
        for message in (secret + ' raw transcript entire payload',
                        'Alpha Vantage Information: ' + secret + ' raw payload'):
            with patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': secret}), patch(
                'src.dashboard.research_adapter.run_stock_research', side_effect=ValueError(message)) as pipeline:
                with self.assertLogs('src.dashboard.research_adapter', level='ERROR') as logs:
                    with self.assertRaises(ResearchRunError): run_research('AAPL')
                pipeline.assert_called_once()
            for text in logs.output:
                self.assertNotIn(secret, text)
                self.assertNotIn('raw payload', text)
                self.assertNotIn('raw transcript', text)

    def test_stage_from_traceback_without_locals(self):
        from src.dashboard.research_adapter import _diagnostic
        namespace = {'__name__': 'src.synthesis'}
        exec('def fail():\n    raise ValueError("OpenAI returned invalid synthesis JSON.")', namespace)
        try:
            namespace['fail']()
        except ValueError as error:
            stage, message = _diagnostic(error)
        self.assertEqual(stage, 'SYNTHESIS')
        self.assertEqual(message, 'OpenAI returned invalid synthesis JSON.')


class EnvironmentBootstrapTests(unittest.TestCase):
    def test_literal_credentials_and_environment_precedence(self):
        import os
        import tempfile
        from src.configuration import load_local_environment
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('export ALPHA_VANTAGE_API_KEY="fixture-av"\nOPENAI_API_KEY=fixture-ai # comment\nUNRELATED=ignored\n')
            load_local_environment(path)
            self.assertEqual(os.environ['ALPHA_VANTAGE_API_KEY'], 'fixture-av')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'fixture-ai')
            self.assertNotIn('UNRELATED', os.environ)
            os.environ['OPENAI_API_KEY'] = 'shell-fixture'
            load_local_environment(path)
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'shell-fixture')

    def test_missing_credentials_keep_client_checks(self):
        import os
        import tempfile
        from src.configuration import load_local_environment
        from src.alpha_vantage_client import get_company_overview
        from src.openai_client import request_text
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            load_local_environment(Path(directory) / 'absent')
            with self.assertRaisesRegex(RuntimeError, 'ALPHA_VANTAGE_API_KEY must be configured'):
                get_company_overview('TEST')
            with self.assertRaisesRegex(RuntimeError, 'OPENAI_API_KEY must be configured'):
                request_text(input='unused', max_output_tokens=1)

    def test_dashboard_bootstrap_without_provider_calls(self):
        import os
        from streamlit.testing.v1 import AppTest
        def bootstrap():
            os.environ['ALPHA_VANTAGE_API_KEY'] = 'fixture-av'
            os.environ['OPENAI_API_KEY'] = 'fixture-ai'
        with patch.dict(os.environ, {}, clear=True), patch('src.configuration.load_local_environment', side_effect=bootstrap) as loader, patch('src.dashboard.research_adapter.run_stock_research') as pipeline:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
            self.assertFalse(app.exception)
            loader.assert_called_once()
            pipeline.assert_not_called()
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'fixture-ai')
            self.assertEqual(os.environ['ALPHA_VANTAGE_API_KEY'], 'fixture-av')

    def test_invalid_file_error_contains_no_secret(self):
        import os
        import tempfile
        from src.configuration import load_local_environment
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('OPENAI_API_KEY="private-fixture\n')
            with self.assertRaises(RuntimeError) as error: load_local_environment(path)
            self.assertNotIn('private-fixture', str(error.exception))
            self.assertNotIn('OPENAI_API_KEY', os.environ)


class PortfolioWorkspaceTests(unittest.TestCase):
    def setUp(self):
        from src.models import PortfolioInput, PortfolioPositionInput
        from src.portfolio_calculations import build_portfolio_snapshot
        from src.portfolio_risk import assess_portfolio_risk
        self.snapshot = build_portfolio_snapshot(PortfolioInput([PortfolioPositionInput('TEST', 2, 10)], 100), {'TEST': 15})
        self.risk = assess_portfolio_risk(self.snapshot)
        for target in ('socket.socket.connect', 'src.research_pipeline.run_stock_research',
                       'src.openai_client.request_text', 'src.decision_store.DecisionStore.save_decision'):
            guard = patch(target, side_effect=AssertionError('Unexpected side effect'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_mapping_without_recalculation(self):
        from dataclasses import asdict
        from src.dashboard.portfolio_adapter import portfolio_page_data, position_rows
        data = portfolio_page_data(self.snapshot, self.risk)
        self.assertIs(data.snapshot, self.snapshot)
        self.assertIs(data.risk_assessment, self.risk)
        self.assertEqual(position_rows(data), [asdict(self.snapshot.positions[0])])
        self.assertEqual(data.snapshot.total_portfolio_value, 130)

    def test_explicit_loader_and_invalid_inputs(self):
        from src.dashboard.portfolio_adapter import load_portfolio, PortfolioLoadError
        with patch('src.dashboard.portfolio_adapter.build_live_portfolio_snapshot', return_value=self.snapshot) as loader:
            data = load_portfolio(' test:2:10 ', 100)
            loader.assert_called_once()
            self.assertEqual(data.snapshot, self.snapshot)
            loader.reset_mock()
            for value, cash in [(':2:10', 0), ('TEST:abc:10', 0), ('TEST:2:10,TEST:1:2', 0), ('', -1)]:
                with self.assertRaises(PortfolioLoadError): load_portfolio(value, cash)
            loader.assert_not_called()

    def test_empty_and_missing_price(self):
        from src.dashboard.portfolio_adapter import load_portfolio
        with patch('src.portfolio_data.get_portfolio_prices', return_value={}):
            empty = load_portfolio('', 100)
            missing = load_portfolio('TEST:2:10', 100)
        self.assertEqual(empty.snapshot.positions, [])
        self.assertEqual(empty.snapshot.total_portfolio_value, 100)
        self.assertIsNone(missing.snapshot.total_portfolio_value)
        self.assertFalse(missing.risk_assessment.concentration_policy_evaluable)

    def test_form_session_and_rendering(self):
        from streamlit.testing.v1 import AppTest
        with patch('src.configuration.load_local_environment'), patch('src.dashboard.portfolio_adapter.build_live_portfolio_snapshot', return_value=self.snapshot) as loader:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py'), default_timeout=30).run()
            app.sidebar.radio[0].set_value('portfolio').run()
            app.text_area[0].set_value('TEST:2:10').run()
            loader.assert_not_called()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            loader.assert_called_once()
            self.assertEqual(app.metric[0].value, '130.00')
            self.assertTrue(app.dataframe)
            app.run()
            app.sidebar.radio[0].set_value('home').run()
            app.sidebar.radio[0].set_value('portfolio').run()
            loader.assert_called_once()
            self.assertEqual(app.metric[0].value, '130.00')
