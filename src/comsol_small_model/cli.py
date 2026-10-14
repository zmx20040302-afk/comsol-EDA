from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .constraints import load_constraints
from .livelink_builder import write_livelink_script
from .matlab_reader import inspect_matlab_file


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="COMSOL small surrogate model tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect-matlab", help="Read a COMSOL MATLAB builder script")
    inspect_parser.add_argument("path")

    validate_parser = sub.add_parser("validate", help="Validate a constrained model JSON file")
    validate_parser.add_argument("path")

    generate_parser = sub.add_parser("generate-matlab", help="Generate a LiveLink MATLAB script")
    generate_parser.add_argument("constraints")
    generate_parser.add_argument("output")

    train_parser = sub.add_parser("train", help="Train a local small surrogate model")
    train_parser.add_argument("csv")
    train_parser.add_argument("model")
    train_parser.add_argument("--inputs", nargs="+", default=[])
    train_parser.add_argument("--outputs", nargs="+", default=[])
    train_parser.add_argument("--auto", action="store_true", help="Infer input/output columns from the CSV")

    inspect_training_parser = sub.add_parser("inspect-training-csv", help="Inspect a CSV and infer surrogate training columns")
    inspect_training_parser.add_argument("csv")
    inspect_training_parser.add_argument("--inputs", nargs="+", default=[])
    inspect_training_parser.add_argument("--outputs", nargs="+", default=[])

    predict_parser = sub.add_parser("predict", help="Predict using a saved surrogate model")
    predict_parser.add_argument("model")
    predict_parser.add_argument("--inputs", nargs="+", type=float, required=True)

    scan_docs_parser = sub.add_parser("scan-comsol-docs", help="Scan local COMSOL PDF documentation directories")
    scan_docs_parser.add_argument(
        "--root",
        default="D:/COMSOL64/Multiphysics/doc/pdf",
        help="COMSOL PDF documentation root directory",
    )
    scan_docs_parser.add_argument(
        "--output-dir",
        default="generated",
        help="Directory for generated catalog and modeling logic files",
    )

    summarize_case_parser = sub.add_parser("summarize-case", help="Summarize a COMSOL case directory into the local knowledge base")
    summarize_case_parser.add_argument("case_dir")
    summarize_case_parser.add_argument("--title", default=None)
    summarize_case_parser.add_argument("--output-dir", default="generated/case_knowledge")
    summarize_case_parser.add_argument("--memory-path", default="generated/case_memory/case_memory.json")

    query_memory_parser = sub.add_parser("query-memory", help="Query remembered COMSOL cases")
    query_memory_parser.add_argument("query")
    query_memory_parser.add_argument("--memory-path", default="generated/case_memory/case_memory.json")
    query_memory_parser.add_argument("--top-k", type=int, default=5)

    knowledge_system_parser = sub.add_parser("build-knowledge-system", help="Build a cross-case COMSOL knowledge system")
    knowledge_system_parser.add_argument("--memory-path", default="generated/case_memory/case_memory.json")

    plan_model_parser = sub.add_parser("plan-model", help="Generate a COMSOL model construction and analysis plan from remembered cases")
    plan_model_parser.add_argument("requirement")
    plan_model_parser.add_argument("--memory-path", default="generated/case_memory/case_memory.json")
    plan_model_parser.add_argument("--top-k", type=int, default=5)

    list_reference_parser = sub.add_parser("list-reference-reports", help="List saved physics-reference reports")
    list_reference_parser.add_argument("--output-dir", default="generated/reference_reports")
    list_reference_parser.add_argument("--limit", type=int, default=30)

    package_reference_parser = sub.add_parser("package-reference-reports", help="Create a portable workchain package from saved reference reports")
    package_reference_parser.add_argument("report_paths", nargs="+")
    package_reference_parser.add_argument("--output-dir", default="generated/workchain_packages")
    package_reference_parser.add_argument("--title", default="physics_reference_validation")

    validate_workchain_parser = sub.add_parser("validate-workchain", help="Validate a portable reference workchain package")
    validate_workchain_parser.add_argument("package_path")

    archive_workchain_parser = sub.add_parser("archive-workchain", help="Create a ZIP from a valid portable reference workchain package")
    archive_workchain_parser.add_argument("package_path")
    archive_workchain_parser.add_argument("--output-dir", default="generated/workchain_archives")

    validate_archive_parser = sub.add_parser("validate-workchain-archive", help="Validate a portable workchain ZIP without extracting it")
    validate_archive_parser.add_argument("archive_path")

    experiment_parser = sub.add_parser(
        "validate-temperature-experiment",
        help="Compare measured temperatures with COMSOL and a validated surrogate",
    )
    experiment_parser.add_argument("csv")
    experiment_parser.add_argument("model")
    experiment_parser.add_argument("--config", default=None)
    experiment_parser.add_argument(
        "--output",
        default="generated/experimental_validation/temperature_validation_report.json",
    )

    args = parser.parse_args()

    if args.command == "inspect-matlab":
        print(inspect_matlab_file(args.path).to_json())
    elif args.command == "validate":
        load_constraints(args.path)
        print(json.dumps({"valid": True, "path": args.path}, ensure_ascii=False, indent=2))
    elif args.command == "generate-matlab":
        output = write_livelink_script(args.constraints, args.output)
        print(json.dumps({"generated": str(output)}, ensure_ascii=False, indent=2))
    elif args.command == "train":
        try:
            from .surrogate import auto_train_surrogate, train_surrogate
        except ModuleNotFoundError as exc:
            raise SystemExit(
                f"Missing training dependency: {exc.name}. "
                "Run `pip install -r requirements.txt` inside comsol_training_small_model."
            ) from exc

        if args.auto or not args.inputs or not args.outputs:
            report, inspection = auto_train_surrogate(args.csv, args.model, args.inputs or None, args.outputs or None)
            print(json.dumps({"inspection": inspection, "report": asdict(report)}, ensure_ascii=False, indent=2))
        else:
            report = train_surrogate(args.csv, args.model, args.inputs, args.outputs)
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.command == "inspect-training-csv":
        try:
            from .surrogate import inspect_training_csv
        except ModuleNotFoundError as exc:
            raise SystemExit(
                f"Missing training dependency: {exc.name}. "
                "Run `pip install -r requirements.txt` inside comsol_training_small_model."
            ) from exc

        print(json.dumps(inspect_training_csv(args.csv, args.inputs or None, args.outputs or None), ensure_ascii=False, indent=2))
    elif args.command == "predict":
        try:
            from .surrogate import predict
        except ModuleNotFoundError as exc:
            raise SystemExit(
                f"Missing prediction dependency: {exc.name}. "
                "Run `pip install -r requirements.txt` inside comsol_training_small_model."
            ) from exc

        print(json.dumps(predict(args.model, args.inputs), ensure_ascii=False, indent=2))
    elif args.command == "scan-comsol-docs":
        from .comsol_knowledge import scan_pdf_root, write_catalog_outputs

        catalog = scan_pdf_root(args.root)
        outputs = write_catalog_outputs(catalog, args.output_dir)
        print(
            json.dumps(
                {
                    "catalog": {
                        "module_count": catalog["module_count"],
                        "pdf_count": catalog["pdf_count"],
                        "domain_counts": catalog["domain_counts"],
                    },
                    "outputs": outputs,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "summarize-case":
        from .case_knowledge import summarize_case_directory
        from .case_memory import remember_case

        result = summarize_case_directory(args.case_dir, title=args.title, output_dir=args.output_dir)
        card = result["card"]
        memory = remember_case(card, args.memory_path)
        print(
            json.dumps(
                {
                    "title": card["title"],
                    "training_stage": card["training_stage"],
                    "file_summary": card["file_summary"],
                    "parameters": len(card["parameters"]),
                    "post_learning_summary": card.get("post_learning_summary", {}),
                    "outputs": result["outputs"],
                    "memory": {
                        "path": memory["memory_path"],
                        "case_count": memory["case_count"],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "query-memory":
        from .case_memory import query_memory

        print(json.dumps(query_memory(args.query, args.memory_path, args.top_k), ensure_ascii=False, indent=2))
    elif args.command == "build-knowledge-system":
        from .case_memory import refresh_knowledge_system

        print(json.dumps(refresh_knowledge_system(args.memory_path), ensure_ascii=False, indent=2))
    elif args.command == "plan-model":
        from .case_memory import generate_model_plan

        print(json.dumps(generate_model_plan(args.requirement, args.memory_path, args.top_k), ensure_ascii=False, indent=2))
    elif args.command == "list-reference-reports":
        from .reference_artifacts import list_reference_reports

        print(json.dumps(list_reference_reports(args.output_dir, limit=args.limit), ensure_ascii=False, indent=2))
    elif args.command == "package-reference-reports":
        from .workchain_package import create_reference_workchain_package

        print(json.dumps(create_reference_workchain_package(args.report_paths, args.output_dir, title=args.title), ensure_ascii=False, indent=2))
    elif args.command == "validate-workchain":
        from .workchain_package import validate_reference_workchain_package

        print(json.dumps(validate_reference_workchain_package(args.package_path), ensure_ascii=False, indent=2))
    elif args.command == "archive-workchain":
        from .workchain_package import archive_reference_workchain_package

        print(json.dumps(archive_reference_workchain_package(args.package_path, args.output_dir), ensure_ascii=False, indent=2))
    elif args.command == "validate-workchain-archive":
        from .workchain_package import validate_reference_workchain_archive

        print(json.dumps(validate_reference_workchain_archive(args.archive_path), ensure_ascii=False, indent=2))
    elif args.command == "validate-temperature-experiment":
        from .experimental_validation import validate_temperature_experiment

        report = validate_temperature_experiment(
            args.csv,
            args.model,
            config_path=args.config,
            output_path=args.output,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
