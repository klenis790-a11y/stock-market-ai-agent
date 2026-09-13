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
                         ['home', 'research', 'portfolio', 'agent_room', 'decision_history', 'performance', 'technical_research'])
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
        self.assertTrue(page.availability.backend_supported)
        self.assertFalse(page.availability.data_available)
        self.assertTrue(page.availability.reason)
        self.assertEqual(page.rows, [])
        self.assertEqual(page.summary, {})

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
            self.assertEqual(len(app.sidebar.radio[0].options), 7)
            for key, title in [('home', 'Home'), ('research', 'Research'), ('portfolio', 'Portfolio'),
                               ('agent_room', 'Agent Room'), ('decision_history', 'Decision History'), ('performance', 'Performance')]:
                app.sidebar.radio[0].set_value(key).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.title[0].value, title)
                self.assertFalse(app.metric)
            self.assertIn('No decision-history source selected', app.info[0].value)

    def test_page_modules_import_and_boundaries(self):
        import importlib
        for page in ui.DASHBOARD_PAGES:
            module = importlib.import_module(f'src.dashboard.{page.key}')
            self.assertTrue(callable(module.render))
            tree = ast.parse(Path(module.__file__).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, ('src.ui_contracts', 'src.dashboard.components', 'src.models', 'src.dashboard.research_adapter', 'src.dashboard.portfolio_adapter', 'src.dashboard.research', 'src.dashboard.history_adapter', 'src.dashboard.decision_save_adapter', 'src.dashboard.portfolio', 'src.dashboard.performance_adapter', 'src.dashboard.evaluation', 'src.dashboard'))
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
        from unittest.mock import ANY
        pipeline.assert_called_once_with('TEST', use_multi_agent=True, persist_decision=False,
                                        use_decision_memory=False, on_specialists_complete=ANY)
        self.assertTrue(callable(pipeline.call_args.kwargs['on_specialists_complete']))
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
            from unittest.mock import ANY
            pipeline.assert_called_once_with('TEST', use_multi_agent=True, persist_decision=False,
                                            use_decision_memory=False, on_specialists_complete=ANY)
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

    def test_each_backend_stage_logged_without_retry_or_result(self):
        from src.dashboard.research_adapter import run_research, ResearchRunError
        cases = (
            ('src.alpha_vantage_client', 'RETRIEVAL'),
            ('src.fundamental_analysis', 'FUNDAMENTAL'),
            ('src.risk_analysis', 'RISK'),
            ('src.synthesis', 'SYNTHESIS'),
            ('src.analysis', 'VALIDATION'),
            ('src.multi_agent', 'VALIDATION'),
        )
        for module, expected in cases:
            namespace = {'__name__': module}
            exec('def fail(*args, **kwargs):\n    raise ValueError("Specialist returned a mismatched result.")', namespace)
            result = None
            with self.subTest(module=module), patch(
                'src.dashboard.research_adapter.run_stock_research', side_effect=namespace['fail']
            ) as pipeline, self.assertLogs('src.dashboard.research_adapter', level='ERROR') as logs:
                with self.assertRaises(ResearchRunError) as caught:
                    result = run_research('AAPL')
                pipeline.assert_called_once()
            self.assertIsNone(result)
            self.assertIn('stage=' + expected, logs.output[0])
            self.assertIn('exception=ValueError', logs.output[0])
            self.assertIn('Specialist returned a mismatched result.', logs.output[0])
            self.assertNotIn('mismatched', str(caught.exception))

    def test_nested_risk_parser_retains_stage_and_redacts_allowlisted_text(self):
        from src.dashboard.research_adapter import run_research, ResearchRunError
        parser = {'__name__': 'src.fundamental_analysis'}
        exec('def fail():\n    raise ValueError("Specialist returned a mismatched result.")', parser)
        risk = {'__name__': 'src.risk_analysis', 'parser': parser['fail']}
        exec('def fail(*args, **kwargs):\n    parser()', risk)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'mismatched'}), patch(
            'src.dashboard.research_adapter.run_stock_research', side_effect=risk['fail']
        ), self.assertLogs('src.dashboard.research_adapter', level='ERROR') as logs:
            with self.assertRaises(ResearchRunError): run_research('AAPL')
        self.assertIn('stage=RISK', logs.output[0])
        self.assertIn('[REDACTED]', logs.output[0])
        self.assertNotIn('mismatched', logs.output[0])


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


class SameRunCaptureTests(unittest.TestCase):
    setUp = ResearchWorkspaceTests.setUp

    def test_adapter_captures_ordered_same_run_without_persistence(self):
        from test_v04 import result
        from src.dashboard.research_adapter import run_research
        items = [result(specialist_name='risk'), result(),
                 result(specialist_name='future_test_specialist')]
        def execute(ticker, **options):
            self.assertEqual(ticker, 'TEST')
            self.assertTrue(options['use_multi_agent'])
            self.assertFalse(options['persist_decision'])
            self.assertFalse(options['use_decision_memory'])
            self.assertNotIn('decision_store', options)
            options['on_specialists_complete'](items)
            return self.analysis
        with patch('src.dashboard.research_adapter.run_stock_research', side_effect=execute) as pipeline:
            data = run_research(' test ')
        pipeline.assert_called_once()
        self.assertIs(data.analysis, self.analysis)
        self.assertEqual(data.specialist_results, items)
        self.assertIsNot(data.specialist_results, items)
        self.assertFalse(data.portfolio_context_supplied)
        self.assertFalse(data.memory_context_supplied)
        self.assertTrue(data.availability['specialists'].data_available)

    def test_session_replacement_failure_and_navigation(self):
        from dataclasses import replace
        from test_v04 import result
        from streamlit.testing.v1 import AppTest
        calls = []
        def execute(ticker, **options):
            calls.append(ticker)
            options['on_specialists_complete']([
                result(ticker=ticker, summary='Same-run ' + ticker),
                result(ticker=ticker, specialist_name='risk'),
            ])
            if ticker == 'FAIL':
                raise ValueError('Synthesis failed')
            return replace(self.analysis, ticker=ticker)
        with patch('src.dashboard.research_adapter.run_stock_research', side_effect=execute):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
            app.sidebar.radio[0].set_value('research').run()
            self.assertEqual(calls, [])
            for ticker in ('FIRST', 'SECOND'):
                app.text_input[0].set_value(ticker)
                app.button[0].click().run()
                self.assertFalse(app.exception)
                data = app.session_state['research_result']
                self.assertEqual(data.analysis.ticker, ticker)
                self.assertEqual([x.ticker for x in data.specialist_results], [ticker, ticker])
                self.assertFalse(data.portfolio_context_supplied)
                self.assertFalse(data.memory_context_supplied)
            self.assertEqual(calls, ['FIRST', 'SECOND'])
            app.run()
            app.sidebar.radio[0].set_value('agent_room').run()
            app.sidebar.radio[0].set_value('research').run()
            self.assertEqual(calls, ['FIRST', 'SECOND'])
            self.assertEqual(app.session_state['research_result'].analysis.ticker, 'SECOND')
            app.text_input[0].set_value('FAIL')
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertNotIn('research_result', app.session_state)
            self.assertFalse(app.metric)
            app.run()
            self.assertEqual(calls, ['FIRST', 'SECOND', 'FAIL'])

    def test_real_pipeline_capture_adapter_boundary(self):
        from test_v04 import result
        from src.models import MultiAgentSynthesisContext
        from src.dashboard.research_adapter import run_research
        items = [result(), result(specialist_name='risk')]
        with patch('src.research_pipeline.build_stock_evidence', return_value={'ticker': 'TEST'}), \
                patch('src.research_pipeline.run_specialists', return_value=MultiAgentSynthesisContext('TEST', items)) as specialists, \
                patch('src.research_pipeline.synthesize_investment_analysis', return_value=self.analysis) as synthesis, \
                patch('src.research_pipeline.save_analysis_decision') as save, \
                patch('src.research_pipeline.build_decision_memory_context') as memory:
            data = run_research('TEST')
        self.assertEqual(data.specialist_results, items)
        self.assertIs(data.analysis, self.analysis)
        specialists.assert_called_once()
        synthesis.assert_called_once()
        save.assert_not_called()
        memory.assert_not_called()


class AgentRoomTests(unittest.TestCase):
    def setUp(self):
        ResearchWorkspaceTests.setUp(self)
        self.guards = []
        for target in (
            'src.dashboard.research_adapter.run_stock_research',
            'src.research_pipeline.run_stock_research',
            'src.research_pipeline.build_stock_evidence',
            'src.research_pipeline.run_specialists',
            'src.research_pipeline.synthesize_investment_analysis',
            'src.fundamental_analysis.request_text',
            'src.risk_analysis.request_text', 'src.synthesis.request_text',
            'src.openai_client.request_text',
            'src.alpha_vantage_client.get_company_overview',
            'src.decision_store.DecisionStore.save_decision',
            'src.decision_store.DecisionStore.get_decisions_for_ticker',
        ):
            guard = patch(target, side_effect=AssertionError('Agent Room must be read-only'))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def app(self, data=None):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        if data is not None:
            app.session_state['research_result'] = data
        app.sidebar.radio[0].set_value('agent_room').run()
        self.assertFalse(app.exception)
        return app

    def data(self, ticker='AAPL', **flags):
        from dataclasses import replace
        from test_v04 import result
        return ui.ResearchPageData(
            analysis=replace(self.analysis, ticker=ticker, confidence_score=63),
            specialist_results=[
                result(ticker=ticker, specialist_name=name, summary=ticker + ' ' + name,
                       confidence_score=score,
                       key_findings=[InterpretationStatement('Current finding ' + name, ['E338', 'E339'])],
                       risks=[InterpretationStatement('Current vulnerability ' + name, ['E340'])],
                       scenarios=[ForecastStatement('Future scenario ' + name, ['E338'])],
                       missing_data=['Missing input ' + name])
                for name, score in [('risk', 70), ('future_test_specialist', 41), ('fundamental', 82)]
            ], **flags)

    def test_empty_and_missing_specialist_capture(self):
        app = self.app()
        self.assertEqual(app.info[0].value, 'No multi-agent research run is available in this session.')
        self.assertIn('Run a company analysis from Research first.', [x.value for x in app.markdown])
        self.assertFalse(app.metric)
        app.session_state['research_result'] = ui.ResearchPageData(analysis=self.analysis)
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)
        self.assertEqual(app.info[0].value, 'No multi-agent research run is available in this session.')

    def test_generic_order_details_provenance_and_synthesis(self):
        from copy import deepcopy
        data = self.data()
        original = deepcopy(data)
        app = self.app(data)
        names = [x.specialist_name for x in data.specialist_results]
        headings = [x.value for x in app.subheader]
        self.assertEqual([x for x in headings if x in names], names)
        self.assertIn('AAPL', headings)
        self.assertIn('Portfolio Manager / Final Synthesis', headings)
        self.assertEqual(app.metric[0].value, data.analysis.recommendation)
        self.assertEqual(app.metric[1].value, '63/100')
        self.assertEqual([x.value for x in app.metric if x.label == 'Specialist confidence'],
                         ['70/100', '41/100', '82/100'])
        self.assertEqual([x.value for x in app.metric if x.label == 'Final synthesis confidence'],
                         ['63/100', '63/100'])
        text = [x.value for x in app.markdown]
        captions = [x.value for x in app.caption]
        for item in data.specialist_results:
            self.assertIn(item.summary, text)
            for statement in item.key_findings + item.risks + item.scenarios:
                self.assertIn(statement.text, text)
                self.assertIn('Evidence references: ' + ', '.join(statement.evidence_refs), captions)
            self.assertIn(item.missing_data[0], [x.value for x in app.warning])
        details = app.expander[0]
        self.assertIn('FORECAST', [x.value for x in details.caption])
        self.assertEqual([x.value for x in details.caption if x.value in ('AI INTERPRETATION', 'FORECAST')],
                         ['AI INTERPRETATION', 'AI INTERPRETATION', 'FORECAST'])
        self.assertIn(data.analysis.reasoning_summary, text)
        for items in (data.analysis.bull_case, data.analysis.bear_case,
                      data.analysis.major_risks, data.analysis.thesis_invalidation_conditions):
            for item in items:
                self.assertIn(item.text, text)
        labels = [x.label for x in app.expander]
        for title in ('Bull case', 'Bear case', 'Major risks · current vulnerabilities',
                      'Thesis invalidation · future observations'):
            self.assertIn(title, labels)
        self.assertTrue(any('catalog resolution is unavailable' in x for x in captions))
        self.assertFalse(app.get('chat_message'))
        self.assertFalse(app.button)
        self.assertEqual(data, original)

    def test_context_flags_only_from_same_run(self):
        app = self.app(self.data())
        # Unrelated page state must never supply provenance for this run.
        app.session_state['portfolio_result'] = 'unrelated portfolio'
        app.run()
        self.assertIn('Portfolio context: Not supplied', [x.value for x in app.caption])
        self.assertIn('Historical memory: Not supplied', [x.value for x in app.caption])
        app.session_state['research_result'] = self.data(portfolio_context_supplied=True,
                                                       memory_context_supplied=True)
        app.run()
        self.assertIn('Portfolio context: Supplied', [x.value for x in app.caption])
        self.assertIn('Historical memory: Supplied', [x.value for x in app.caption])

    def test_session_replacement_navigation_and_reruns(self):
        app = self.app(self.data('AAPL'))
        app.run()
        app.sidebar.radio[0].set_value('home').run()
        app.sidebar.radio[0].set_value('agent_room').run()
        self.assertIn('AAPL', [x.value for x in app.subheader])
        app.session_state['research_result'] = self.data('NVDA')
        app.run()
        self.assertFalse(app.exception)
        self.assertIn('NVDA', [x.value for x in app.subheader])
        self.assertNotIn('AAPL', [x.value for x in app.subheader])
        self.assertFalse(any('AAPL' in x.value for x in app.markdown))
        del app.session_state['research_result']
        app.run()
        self.assertFalse(app.metric)
        self.assertIn('No multi-agent research run', app.info[0].value)

    def test_empty_details_and_catalog_presence_are_honest(self):
        data = self.data()
        item = data.specialist_results[0]
        item.key_findings = []
        item.risks = []
        item.scenarios = []
        item.missing_data = []
        data.specialist_results = [item]
        data.evidence_catalog = []
        app = self.app(data)
        self.assertFalse(app.exception)
        self.assertFalse(app.warning)
        self.assertIn('No entries supplied.', [x.value for x in app.expander[0].caption])
        self.assertTrue(any('No missing data reported' in x.value for x in app.caption))
        self.assertTrue(any('references only' in x.value for x in app.caption))


class HistoryDashboardTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from src.decision_store import DecisionStore
        from test_v03 import record, outcome
        ResearchWorkspaceTests.setUp(self)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'history.db'
        self.store = DecisionStore(str(self.path))
        self.store.initialize()
        self.old = record(decision_id='old', ticker='AAPL', decision_timestamp='2026-01-01')
        self.new = record(decision_id='new', ticker='AAPL', decision_timestamp='2026-02-01',
                          recommendation='Accumulate', confidence_score=67.5,
                          reasoning_summary='Preserved original thesis', portfolio_assessment='Stored portfolio assessment',
                          bear_case=[InterpretationStatement('Historical bear', ['E010'])],
                          major_risks=[InterpretationStatement('Historical risk', ['E011'])],
                          thesis_invalidation_conditions=[ForecastStatement('Original invalidation condition', ['E012'])],
                          missing_data=['Historical missing evidence'])
        for item in (self.old, self.new, record(decision_id='other', ticker='MSFT')):
            self.store.save_decision(item)
        self.outcome = outcome(decision_id='new', evaluation_timestamp='2027-02-01',
                               evaluation_horizon='1 year', stock_return=-0.1,
                               benchmark_ticker='VOO', benchmark_start_price=50,
                               benchmark_end_price=55, benchmark_return=0.1, excess_return=-0.2)
        self.store.save_outcome(self.outcome)
        self.before = self.path.read_bytes()
        self.guards = []
        for target in ('src.dashboard.research_adapter.run_stock_research',
                       'src.research_pipeline.run_stock_research',
                       'src.alpha_vantage_client._request', 'src.openai_client.request_text',
                       'src.decision_memory.build_decision_memory_context',
                       'src.decision_store.DecisionStore.initialize',
                       'src.decision_store.DecisionStore.save_decision',
                       'src.decision_store.DecisionStore.save_outcome'):
            guard = patch(target, side_effect=AssertionError('History must only read'))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def test_missing_empty_invalid_and_unknown_selection(self):
        from src.dashboard.history_adapter import load_history, select_decision, HistoryReadError
        missing = self.path.parent / 'absent.db'
        data = load_history(str(missing), 'AAPL')
        self.assertFalse(data.availability['history'].data_available)
        self.assertFalse(missing.exists())
        self.assertEqual(load_history(str(self.path), 'NONE').decisions, [])
        for path, ticker in (('', 'AAPL'), (str(self.path), '  ')):
            with self.assertRaises(HistoryReadError):
                load_history(path, ticker)
        self.assertIsNone(select_decision(load_history(str(self.path), 'AAPL'), 'unknown'))

    def test_records_order_filter_outcomes_and_read_only(self):
        from src.dashboard.history_adapter import load_history, select_decision
        from src.decision_store import DecisionStore
        with patch('src.dashboard.history_adapter.DecisionStore', wraps=DecisionStore) as factory:
            data = load_history(str(self.path), ' aapl ')
        factory.assert_called_once_with(str(self.path), read_only=True)
        self.assertEqual(data.decisions, [self.new, self.old])
        self.assertEqual(select_decision(data, 'new'), self.new)
        self.assertEqual(data.outcomes, [self.outcome])
        self.assertIsNone(data.memory_context)
        self.assertEqual(self.store.get_decision('new'), self.new)
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual({p.name for p in self.path.parent.iterdir()}, {'history.db'})

    def test_corrupt_and_unreadable_database_sanitized(self):
        import sqlite3
        from src.dashboard.history_adapter import load_history, HistoryReadError
        corrupt = self.path.parent / 'corrupt.db'
        corrupt.write_text('sensitive database content')
        with self.assertRaises(HistoryReadError) as caught:
            load_history(str(corrupt), 'AAPL')
        self.assertNotIn('sensitive', str(caught.exception))
        with patch('src.dashboard.history_adapter.DecisionStore.get_decisions_for_ticker',
                   side_effect=sqlite3.OperationalError('secret permission detail')):
            with self.assertRaises(HistoryReadError) as caught:
                load_history(str(self.path), 'AAPL')
        self.assertNotIn('secret', str(caught.exception))
        # Corrupt a separate fixture so the original history remains intact.
        corrupt.write_bytes(self.before)
        with sqlite3.connect(corrupt) as connection:
            connection.execute('UPDATE decisions SET bull_case = ? WHERE decision_id = ?',
                               ('secret invalid JSON', 'new'))
        with self.assertRaises(HistoryReadError) as caught:
            load_history(str(corrupt), 'AAPL')
        self.assertNotIn('secret', str(caught.exception))

    def test_page_selection_temporal_gaps_and_no_mutation(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        app.session_state['research_result'] = ui.ResearchPageData(analysis=self.analysis,
                                                                  evidence_catalog=[{'current': 'NEVER USE CURRENT DATA'}])
        app.sidebar.radio[0].set_value('decision_history').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.dataframe)
        app.text_input[0].set_value(str(self.path))
        app.text_input[1].set_value(' aapl ')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value['Decision ID'].tolist(), ['new', 'old'])
        self.assertEqual(app.metric[0].value, 'Accumulate')
        self.assertEqual(app.metric[1].value, '67.5/100')
        text = [x.value for x in app.markdown]
        self.assertIn('Decision made: 2026-02-01', text)
        self.assertIn('Evaluation timestamp: 2027-02-01', text)
        self.assertIn(self.new.reasoning_summary, text)
        self.assertIn(self.new.portfolio_assessment, text)
        self.assertIn('Historical risk', text)
        self.assertIn('Original invalidation condition', text)
        self.assertTrue(any('Not preserved in this historical record' in x.value for x in app.info))
        self.assertFalse(any('NEVER USE CURRENT DATA' in x for x in text))
        outcome_rows = app.table[0].value
        self.assertEqual(outcome_rows.loc[outcome_rows['Stored outcome field'] == 'stock return', 'Value'].iloc[0], '-0.1')
        self.assertIn('Later outcomes · separate observations', [x.value for x in app.subheader])
        app.selectbox[0].select('old').run()
        self.assertEqual(app.metric[0].value, self.old.recommendation)
        self.assertIn('No stored outcomes for this decision.', [x.value for x in app.info])
        app.run()
        app.sidebar.radio[0].set_value('home').run()
        app.sidebar.radio[0].set_value('decision_history').run()
        self.assertEqual(app.selectbox[0].value, 'old')
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(self.store.get_decision('new'), self.new)
        self.assertEqual(self.store.get_outcomes_for_decision('new'), [self.outcome])

    def test_new_source_failure_clears_old_display(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        app.session_state['history_query'] = (str(self.path), 'AAPL')
        app.sidebar.radio[0].set_value('decision_history').run()
        self.assertTrue(app.metric)
        app.text_input[0].set_value(str(self.path.parent / 'missing.db'))
        app.text_input[1].set_value('MSFT')
        app.button[0].click().run()
        self.assertFalse(app.metric)
        self.assertFalse(app.exception)
        self.assertIn('No database was created', app.info[0].value)
        self.assertEqual(self.path.read_bytes(), self.before)


class DecisionSaveTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        ResearchWorkspaceTests.setUp(self)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'decisions.db'
        from src.dashboard.research_adapter import run_research
        with patch('src.dashboard.research_adapter.run_stock_research', return_value=self.analysis):
            self.data = run_research('TEST')

    def test_mapping_timestamp_history_and_duplicate(self):
        from src.dashboard.decision_save_adapter import save_research_decision, DecisionSaveError
        from src.decision_history import save_analysis_decision
        from src.dashboard.history_adapter import load_history
        from copy import deepcopy
        original = deepcopy(self.data)
        with patch('src.dashboard.decision_save_adapter.utc_decision_timestamp', return_value='20260911T120000.000000Z') as clock, \
                patch('src.dashboard.decision_save_adapter.save_analysis_decision', wraps=save_analysis_decision) as save:
            record = save_research_decision(self.data, str(self.path))
        clock.assert_called_once()
        save.assert_called_once()
        self.assertIs(save.call_args.args[0], self.analysis)
        self.assertEqual(record.decision_timestamp, '20260911T120000.000000Z')
        for field in fields(self.analysis):
            self.assertEqual(getattr(record, field.name), getattr(self.analysis, field.name))
        history = load_history(str(self.path), 'TEST')
        self.assertEqual(history.decisions, [record])
        self.assertEqual(history.outcomes, [])
        self.assertEqual(original, self.data)
        with self.assertRaises(DecisionSaveError):
            save_research_decision(self.data, str(self.path), decision_id=record.decision_id,
                                   decision_timestamp=record.decision_timestamp)
        self.assertEqual(load_history(str(self.path), 'TEST').decisions, [record])

    def test_invalid_and_persistence_error_sanitized(self):
        import sqlite3
        from src.dashboard.decision_save_adapter import save_research_decision, DecisionSaveError
        with patch('src.dashboard.decision_save_adapter.DecisionStore') as store:
            for data, path in ((None, str(self.path)), (ui.ResearchPageData(), str(self.path)),
                               (self.data, ''), (self.data, 'https://invalid'), (self.data, ':memory:')):
                with self.assertRaises(DecisionSaveError):
                    save_research_decision(data, path)
            store.assert_not_called()
        with patch('src.dashboard.decision_save_adapter.DecisionStore.initialize',
                   side_effect=sqlite3.OperationalError('secret error detail')):
            with self.assertRaises(DecisionSaveError) as caught:
                save_research_decision(self.data, str(self.path))
        self.assertNotIn('secret', str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_explicit_save_reruns_navigation_and_new_failed_run(self):
        from streamlit.testing.v1 import AppTest
        from src.dashboard.history_adapter import load_history
        with patch('src.dashboard.research_adapter.run_stock_research', return_value=self.analysis) as pipeline, \
                patch('src.alpha_vantage_client._request', side_effect=AssertionError('No provider')) as av, \
                patch('src.openai_client.request_text', side_effect=AssertionError('No AI')) as ai, \
                patch('src.decision_memory.build_decision_memory_context', side_effect=AssertionError('No memory')) as memory:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
            app.sidebar.radio[0].set_value('research').run()
            self.assertNotIn('Save Decision', [x.label for x in app.button])
            app.text_input[0].set_value('TEST')
            app.button[0].click().run()
            self.assertFalse(self.path.exists())
            self.assertIn('Save Decision', [x.label for x in app.button])
            app.text_input[0].set_value('UNSUBMITTED')
            app.text_input[1].set_value(str(self.path))
            app.button[1].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            pipeline.assert_called_once()
            records = load_history(str(self.path), 'TEST').decisions
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].ticker, self.analysis.ticker)
            app.run()
            app.sidebar.radio[0].set_value('agent_room').run()
            app.sidebar.radio[0].set_value('research').run()
            self.assertEqual(len(load_history(str(self.path), 'TEST').decisions), 1)
            app.text_input[1].set_value(str(self.path))
            app.button[1].click().run()
            self.assertTrue(app.error)
            self.assertFalse(app.success)
            self.assertEqual(len(load_history(str(self.path), 'TEST').decisions), 1)
            pipeline.side_effect = RuntimeError('Failed research')
            app.text_input[0].set_value('FAILED')
            app.button[0].click().run()
            self.assertNotIn('Save Decision', [x.label for x in app.button])
            self.assertNotIn('saved_decision', app.session_state)
            self.assertEqual(load_history(str(self.path), 'TEST').outcomes, [])
            av.assert_not_called()
            ai.assert_not_called()
            memory.assert_not_called()


class HomeOverviewTests(unittest.TestCase):
    def setUp(self):
        ResearchWorkspaceTests.setUp(self)
        self.guards = []
        for target in ('src.dashboard.research_adapter.run_stock_research',
                       'src.alpha_vantage_client._request', 'src.openai_client.request_text',
                       'src.research_pipeline.run_specialists',
                       'src.research_pipeline.synthesize_investment_analysis',
                       'src.decision_store.DecisionStore.initialize',
                       'src.decision_store.DecisionStore.save_decision',
                       'src.decision_store.DecisionStore.save_outcome'):
            guard = patch(target, side_effect=AssertionError('Home must not execute investment work'))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()

    def test_empty_and_navigation_only(self):
        with patch('src.dashboard.home.load_history', side_effect=AssertionError('No unknown history source')):
            app = self.app()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)
            messages = [x.value for x in app.info]
            self.assertIn('No portfolio loaded in this session.', messages)
            self.assertIn('No company research has been run in this session.', messages)
            self.assertIn('No decision-history source selected.', messages)
            self.assertTrue(any('Open Performance to inspect stored outcome summaries' in x.value for x in app.caption))
            for label, destination in [('Research a ticker', 'research'), ('View Portfolio', 'portfolio'),
                                       ('Inspect Agent Room', 'agent_room'), ('View Decision History', 'decision_history')]:
                next(x for x in app.button if x.label == label).click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.sidebar.radio[0].value, destination)
                app.sidebar.radio[0].set_value('home').run()

    def test_existing_values_flags_generic_count_and_no_mutation(self):
        from copy import deepcopy
        from test_v04 import result
        from src.models import PortfolioInput, PortfolioPositionInput
        from src.portfolio_calculations import build_portfolio_snapshot
        from src.portfolio_risk import assess_portfolio_risk
        snapshot = build_portfolio_snapshot(PortfolioInput([PortfolioPositionInput('TEST', 2, 20)], 10), {'TEST': 30})
        portfolio = ui.PortfolioPageData(snapshot=snapshot, risk_assessment=assess_portfolio_risk(snapshot))
        research = ui.ResearchPageData(analysis=self.analysis,
                    specialist_results=[result(), result(specialist_name='risk'), result(specialist_name='future_test_specialist')],
                    portfolio_context_supplied=True, memory_context_supplied=False)
        before = deepcopy((portfolio, research))
        app = self.app()
        app.session_state['portfolio_result'] = portfolio
        app.session_state['research_result'] = research
        with patch('src.portfolio_calculations.build_portfolio_snapshot', side_effect=AssertionError('No recalculation')):
            app.run()
        self.assertFalse(app.exception)
        metrics = {x.label: x.value for x in app.metric}
        self.assertEqual(metrics['Total portfolio value'], f'{snapshot.total_portfolio_value:,.2f}')
        self.assertEqual(metrics['Positions value'], f'{snapshot.total_positions_value:,.2f}')
        self.assertEqual(metrics['Cash'], f'{snapshot.cash:,.2f}')
        self.assertEqual(metrics['Recommendation'], self.analysis.recommendation)
        self.assertEqual(metrics['Final synthesis confidence'], f'{self.analysis.confidence_score}/100')
        captions = [x.value for x in app.caption]
        self.assertTrue(any('3 specialists completed' in x for x in captions))
        self.assertTrue(any('Portfolio context: Supplied · Historical memory: Not supplied' == x for x in captions))
        self.assertEqual([x.value for x in app.warning], portfolio.risk_assessment.notes)
        self.assertEqual((portfolio, research), before)

    def test_known_history_source_read_only_and_missing(self):
        import tempfile
        from src.decision_store import DecisionStore
        from test_v03 import record
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.db'
            # A selected source is forwarded exactly; unknown sources are never queried.
            with patch('src.dashboard.home.load_history') as load:
                load.return_value = ui.DecisionHistoryPageData(decisions=[record(ticker='OLD', recommendation='Trim')])
                app = self.app()
                load.assert_not_called()
                app.session_state['history_query'] = (str(path), 'OLD')
                app.run()
                load.assert_called_once_with(str(path), 'OLD')
                self.assertTrue(any('OLD · 2026-01-01 · Trim · Confidence: 60/100' == x.value for x in app.markdown))
                self.assertFalse(path.exists())
            app.run()
            self.assertFalse(path.exists())
            self.assertTrue(any('No database was created' in x.value for x in app.info))


class PerformanceDashboardTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from src.decision_store import DecisionStore
        from test_v03 import record, outcome
        ResearchWorkspaceTests.setUp(self)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'performance.db'
        self.store = DecisionStore(str(self.path))
        self.store.initialize()
        self.records = []
        self.outcomes = []
        for i, stock in enumerate((0.2, -0.1, 0.0, 0.4, 0.5, None)):
            item = record(decision_id=str(i), ticker='TEST', recommendation='Buy' if i < 3 else 'Avoid', confidence_score=45 if i < 3 else 85)
            later = outcome(decision_id=str(i), evaluation_horizon='custom horizon' if i < 3 else '1 year',
                            stock_return=stock, benchmark_return=0.1 if i in (0, 1, 5) else None,
                            excess_return=0.1 if i == 0 else -0.2 if i == 1 else None,
                            benchmark_ticker='VOO' if i in (0, 1, 5) else None)
            self.store.save_decision(item)
            self.store.save_outcome(later)
            self.records.append(item)
            self.outcomes.append(later)
        self.before = self.path.read_bytes()
        self.guards = []
        for target in ('src.alpha_vantage_client._request', 'src.openai_client.request_text',
                       'src.dashboard.research_adapter.run_stock_research',
                       'src.decision_store.DecisionStore.initialize',
                       'src.decision_store.DecisionStore.save_decision',
                       'src.decision_store.DecisionStore.save_outcome'):
            guard = patch(target, side_effect=AssertionError('Read-only evaluation'))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_stored_aggregates_denominators_and_groups(self):
        from src.dashboard.performance_adapter import load_performance
        data = load_performance(str(self.path), ' test ')
        self.assertEqual(len(data.rows), 6)
        self.assertEqual(data.summary['stock_return_count'], 5)
        self.assertAlmostEqual(data.summary['average_stock_return'], 0.2)
        self.assertEqual(data.summary['benchmark_return_count'], 3)
        self.assertAlmostEqual(data.summary['average_benchmark_return'], 0.1)
        self.assertEqual(data.summary['excess_return_count'], 2)
        self.assertAlmostEqual(data.summary['average_excess_return'], -0.05)
        self.assertEqual(data.summary['positive_return_count'], 3)
        self.assertEqual(data.summary['positive_return_rate'], 0.6)
        self.assertEqual(data.summary['benchmark_outperformance_count'], 1)
        self.assertEqual(data.summary['benchmark_outperformance_rate'], 0.5)
        self.assertEqual(set(data.recommendations), {'Buy', 'Avoid'})
        self.assertEqual(set(data.horizons), {'custom horizon', '1 year'})
        self.assertEqual(set(data.confidence_groups), {'0–49', '80–89'})
        for original in self.records:
            self.assertEqual(self.store.get_decision(original.decision_id), original)
        for original in self.outcomes:
            self.assertEqual(self.store.get_outcome(original.decision_id, original.evaluation_horizon), original)

    def test_no_source_missing_no_returns_and_single(self):
        from src.dashboard.performance_adapter import load_performance, summarize, confidence_bucket
        self.assertFalse(load_performance('', '').availability.data_available)
        missing = self.path.parent / 'absent.db'
        self.assertFalse(load_performance(str(missing), 'TEST').availability.data_available)
        self.assertFalse(missing.exists())
        history = ui.DecisionHistoryPageData(decisions=[self.records[0]],
            availability={'history': ui.UISectionAvailability(True, True)})
        with patch('src.dashboard.performance_adapter.load_history', return_value=history):
            empty = load_performance(str(self.path), 'TEST')
            self.assertIn('No evaluated decision outcomes', empty.availability.reason)
            self.assertEqual(empty.summary, {})
            history.outcomes = [self.outcomes[0]]
            self.assertEqual(load_performance(str(self.path), 'TEST').summary['stock_return_count'], 1)
        summary = summarize([{'stock_return': None, 'benchmark_return': float('nan'), 'excess_return': float('inf')}])
        self.assertIsNone(summary['average_stock_return'])
        self.assertIsNone(summary['average_benchmark_return'])
        self.assertIsNone(summary['benchmark_outperformance_rate'])
        self.assertEqual([confidence_bucket(x) for x in (49.9, 50, 90, 100)], ['0–49', '50–59', '90–100', '90–100'])

    def test_page_charts_sample_warning_and_read_only(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard.py')).run()
        app.sidebar.radio[0].set_value('performance').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)
        self.assertFalse(app.get('vega_lite_chart'))
        self.assertIn('No decision-history source selected', app.info[0].value)
        app.text_input[0].set_value(str(self.path))
        app.text_input[1].set_value('TEST')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '5')
        self.assertTrue(app.warning)
        self.assertEqual(len(app.dataframe), 4)
        self.assertTrue(app.get('vega_lite_chart'))
        app.run()
        from src.dashboard.performance_adapter import load_performance
        data = load_performance(str(self.path), 'TEST')
        data.summary['stock_return_count'] = 1
        with patch('src.dashboard.performance.load_performance', return_value=data):
            app.run()
            self.assertFalse(app.get('vega_lite_chart'))


class ProviderOperationDiagnosticTests(unittest.TestCase):
    def test_provider_operations_classification_and_private_ui(self):
        import io, json
        from src import alpha_vantage_client as api
        from src.dashboard.research_adapter import run_research, ResearchRunError
        for function, operation in api._OPERATIONS.items():
            for key, expected in (('Error Message','ERROR_MESSAGE'),('Information','INFORMATION'),('Note','NOTE')):
                with self.subTest(function=function,key=key), patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY':'fixture-secret'}), patch(
                    'src.alpha_vantage_client.urlopen',return_value=io.BytesIO(json.dumps({key:'fixture-secret raw-private-body'}).encode())) as network, patch(
                    'src.alpha_vantage_client._pace_request'), patch(
                    'src.dashboard.research_adapter.run_stock_research',side_effect=lambda *a,**k: api._request(function,'AAPL')), \
                    self.assertLogs(level='ERROR') as logs:
                    with self.assertRaises(ResearchRunError) as caught:run_research('AAPL')
                    network.assert_called_once()
                text=' '.join(logs.output)
                self.assertIn('stage=RETRIEVAL',text)
                self.assertIn('operation='+operation,text)
                self.assertIn('function='+function,text)
                self.assertIn('provider_response_type='+expected,text)
                for private in ('fixture-secret','raw-private-body'):
                    self.assertNotIn(private,text)
                    self.assertNotIn(private,str(caught.exception))

    def test_empty_malformed_network_and_success_unchanged(self):
        import io
        from urllib.error import URLError
        from src import alpha_vantage_client as api
        for body, expected in ((b'{}','EMPTY_RESPONSE'),(b'[]','MALFORMED_RESPONSE'),(b'{','MALFORMED_RESPONSE')):
            with patch.dict('os.environ',{'ALPHA_VANTAGE_API_KEY':'fixture'}), patch('src.alpha_vantage_client._pace_request'), patch('src.alpha_vantage_client.urlopen',return_value=io.BytesIO(body)):
                with self.assertRaises(RuntimeError) as caught:api.get_company_overview('AAPL')
                self.assertEqual(caught.exception.provider_response_type,expected)
        with patch.dict('os.environ',{'ALPHA_VANTAGE_API_KEY':'fixture'}), patch('src.alpha_vantage_client._pace_request'), patch('src.alpha_vantage_client.urlopen',side_effect=URLError('private-url')):
            with self.assertRaises(RuntimeError) as caught:api.get_company_overview('AAPL')
            self.assertEqual(caught.exception.provider_response_type,'NETWORK_ERROR')
        with patch.dict('os.environ',{'ALPHA_VANTAGE_API_KEY':'fixture'}), patch('src.alpha_vantage_client._pace_request'), patch('src.alpha_vantage_client.urlopen',return_value=io.BytesIO(b'{"Symbol":"AAPL"}')) as network:
            self.assertEqual(api.get_company_overview('AAPL'),{'Symbol':'AAPL'})
            network.assert_called_once()
