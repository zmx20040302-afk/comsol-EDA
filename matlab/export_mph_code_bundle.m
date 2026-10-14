function result = export_mph_code_bundle(mphPath, outputDir)
%EXPORT_MPH_CODE_BUNDLE Export a COMSOL MPH file as MATLAB, Java, and JSON.
% The input MPH file is loaded read-only; all generated artifacts go to outputDir.

if nargin < 2 || isempty(outputDir)
    outputDir = fullfile(fileparts(mphPath), [erase(string(mphPath), ".mph") "_exports"]);
end
if ~isfolder(outputDir)
    mkdir(outputDir);
end

[~, baseName, ~] = fileparts(mphPath);
matlabPath = fullfile(outputDir, [baseName '.m']);
javaPath = fullfile(outputDir, [baseName '.java']);
summaryPath = fullfile(outputDir, [baseName '_summary.json']);

model = mphload(mphPath);
% Export the current model tree instead of every historical GUI operation.
% This reduces generated code size and avoids history-save failures on large models.
try
    model.resetHist();
catch
    warning('Could not compact model history; exporting the available history.');
end
% Component syntax makes the exported M-file match the COMSOL model tree.
mphsave(model, matlabPath, 'component', 'on');
model.save(javaPath, 'java');
export_mph_summary(mphPath, summaryPath);

result = struct();
result.source_mph = mphPath;
result.matlab_path = matlabPath;
result.java_path = javaPath;
result.summary_path = summaryPath;
result.message = 'MPH export completed.';
end
