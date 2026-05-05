:: set pd_algorithms=im ilp alpha
:: set window_length=5 10 15
set nreps=2 3 4 5


for /D %%p IN ("Results\*") DO (
	del /s /f /q %%p\*.*
	for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
	rmdir "%%p" /s /q
)

for %%r in (%nreps%) do (

	mkdir Results\%%r

	for /D %%p IN ("Input\*") DO (
		del /s /f /q %%p\*.*
		for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
		rmdir "%%p" /s /q
	)

	del /F /Q Input\*
	
	for /D %%p IN ("Output\*") DO (
		del /s /f /q %%p\*.*
		for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
		rmdir "%%p" /s /q
	)

	del /F /Q Output\*
	
	xcopy Dataset\%%r Input /E

	python conformance_checking.py

	REM ren handover_procedure_logs.json handover_event_logs.json
	
	xcopy Output Results\%%r /E

)

