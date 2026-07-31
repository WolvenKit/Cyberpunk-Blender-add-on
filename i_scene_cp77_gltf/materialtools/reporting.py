def report_materialtools(owner, severity, message):
    severity = str(severity)
    message = str(message)
    reporter = getattr(owner, "report", None)
    if callable(reporter):
        try:
            reporter({severity}, message)
            return
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
    print(f"[CP77 MaterialTools] {severity}: {message}")
