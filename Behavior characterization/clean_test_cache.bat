for /D %%p IN ("__pycache__\*") DO (
	del /s /f /q %%p\*.*
	for /f %%f in ('dir /ad /b %%p') do rd /s /q %%p\%%f
	rmdir "%%p" /s /q
)
del /F /Q __pycache__\*
rmdir __pycache__ /s /q
		
del /F /Q .pytest_cache\*
rmdir .pytest_cache /s /q