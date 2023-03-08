March 2023

The summary hook is an experimental xblock aside which allows us to inject javascript and results from our experimental OpenAI summary service.

The summary hook aside contains almost no smarts itself beyond detecting summarizable content in a unit and reaching out for some javascript if it finds them.

This summarization experiment should be limited to 2023, after which we will either graduate this xblock to its own repository or try another experiment.