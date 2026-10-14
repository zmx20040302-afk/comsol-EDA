function summary = export_mph_summary(mphPath, outputJsonPath)
%EXPORT_MPH_SUMMARY Export a small JSON-like summary from a COMSOL MPH file.
%
% Requirements:
%   - COMSOL Multiphysics
%   - LiveLink for MATLAB
%
% Example:
%   summary = export_mph_summary('model.mph', 'model_summary.json');

import com.comsol.model.*
import com.comsol.model.util.*

model = mphload(mphPath);

summary = struct();
summary.source = mphPath;
summary.label = char(model.label());
summary.parameters = struct();

paramNames = model.param.varnames();
for i = 1:numel(paramNames)
    name = char(paramNames(i));
    summary.parameters.(matlab.lang.makeValidName(name)) = char(model.param.get(name));
end

% Predeclare all fields: MATLAB cannot append a populated struct to a
% zero-field struct array when a model has several components.
summary.components = struct('tag', {}, 'geometry', {}, 'materials', {}, ...
    'physics', {}, 'meshes', {}, 'couplings', {});
componentTags = localTags(model.component);
for i = 1:numel(componentTags)
    tag = componentTags{i};
    component = model.component(tag);
    item = struct();
    item.tag = tag;
    item.geometry = localTags(component.geom);
    item.materials = localTags(component.material);
    item.physics = localTags(component.physics);
    item.meshes = localTags(component.mesh);
    item.couplings = localTags(component.cpl);
    summary.components(end + 1) = item; %#ok<AGROW>
end

summary.studies = localTags(model.study);
summary.result_groups = localTags(model.result);
summary.datasets = localTags(model.result.dataset);
summary.tables = localTags(model.result.table);
summary.exports = localTags(model.result.export);
summary.note = ['The summary contains model-tree tags that can be read by the local COMSOL assistant. ' ...
    'Export Java or MATLAB code as a sidecar when feature properties and entity selections are required.'];

if nargin > 1 && ~isempty(outputJsonPath)
    encoded = jsonencode(summary, PrettyPrint=true);
    fid = fopen(outputJsonPath, 'w');
    cleanup = onCleanup(@() fclose(fid));
    fwrite(fid, encoded, 'char');
end
end

function values = localTags(container)
values = {};
try
    raw = container.tags();
catch
    try
        raw = container.tags;
    catch
        return;
    end
end
if isempty(raw)
    return;
end
if ischar(raw) || isstring(raw)
    values = cellstr(raw);
    return;
end
values = cell(size(raw));
for i = 1:numel(raw)
    values{i} = char(raw(i));
end
end
