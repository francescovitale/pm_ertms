set nreps=1 2 3 4 5


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
	
	xcopy Diagnoses\%%r Input /E

	python anomaly_detection_explanation.py
	
	copy Output\* Results\%%r

)

