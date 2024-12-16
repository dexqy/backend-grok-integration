const { spawn } = require('child_process');
const path = require('path');

const runPythonScript = (command, args) => {
    return new Promise((resolve, reject) => {
        const scriptPath = path.resolve(__dirname, 'scrapper.py');
        console.log(`Executing Python script: ${scriptPath} with command: ${command} and args: ${args}`);

        const pythonProcess = spawn('python', [scriptPath, command, ...args]);

        let scriptOutput = '';
        let scriptError = '';

        pythonProcess.stdout.on('data', (data) => {
            console.log(`Python stdout: ${data}`);
            scriptOutput += data.toString();
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python stderr: ${data}`);
            scriptError += data.toString();
        });

        pythonProcess.on('close', (code) => {
            console.log(`Python process exited with code ${code}`);
            if (code === 0) {
                try {
                    const parsedData = JSON.parse(scriptOutput);
                    resolve(parsedData);
                } catch (error) {
                    console.error(`Error parsing JSON: ${error.message}`);
                    reject(`Error parsing JSON: ${error.message}`);
                }
            } else {
                reject(scriptError);
            }
        });
    });
};

const queryAndRespond = (query) => runPythonScript('query', [query]);
const crawlUrls = (homepage, maxPages) => runPythonScript('crawl', [homepage, maxPages]);
const scrapeUrls = (urls) => runPythonScript('scrape', [JSON.stringify(urls)]);
const storeData = (data) => runPythonScript('store', [JSON.stringify(data)]);

module.exports = { queryAndRespond, crawlUrls, scrapeUrls, storeData };
