set pd_algorithms=im ilp alpha
set nreps=1 2 3 4 5

for /D %%p IN ("Results\TestResults\*") DO (
	del /s /f /q %%p\*.*
	for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
	rmdir "%%p" /s /q
)

mkdir Results\TestResults

for /D %%p IN ("Results\ProcessMiningResults\*") DO (
	del /s /f /q %%p\*.*
	for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
	rmdir "%%p" /s /q
)

mkdir Results\ProcessMiningResults

del /F /Q Input\*
		
pytest test_suite.py -v -s

ren handover_procedure_logs.json handover_event_logs.json
copy handover_event_logs.json Results\TestResults
copy handover_event_logs.json Input
del /F /Q handover_event_logs.json
			
call clean_test_cache


for %%r in (%nreps%) do (

	mkdir Results\ProcessMiningResults\%%r
	
	for /D %%p IN ("Output\GeneratedDataset\*") DO (
		del /s /f /q %%p\*.*
		for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
		rmdir "%%p" /s /q
	)
		
	python generate_dataset.py 0.2
		
	xcopy Output\GeneratedDataset Results\ProcessMiningResults\%%r /E

	for %%a in (%pd_algorithms%) do (
	
		del /F /Q Output\NormativeBehavior\*

		mkdir Results\ProcessMiningResults\%%r\%%a

		python process_mining.py %%a
		
		copy Output\NormativeBehavior\* Results\ProcessMiningResults\%%r\%%a
		
	)

)

	






