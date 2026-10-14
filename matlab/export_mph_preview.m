function preview_file = export_mph_preview(mph_file, preview_file, server_host, server_port)
%EXPORT_MPH_PREVIEW Export a browser-friendly preview from an existing MPH.
%   The function connects to a running COMSOL mphserver, opens MPH_FILE,
%   exports the first available result plot, and falls back to a geometry
%   rendering when the model has no exportable solved result.

import com.comsol.model.util.*

if nargin < 3 || isempty(server_host)
    server_host = 'localhost';
end
if nargin < 4 || isempty(server_port)
    server_port = 2036;
end

mph_file = char(mph_file);
preview_file = char(preview_file);
server_host = char(server_host);
server_port = double(server_port);

if exist(mph_file, 'file') == 0
    error('COMSOLPreview:MissingModel', 'MPH file does not exist: %s', mph_file);
end

preview_parent = fileparts(preview_file);
if ~isempty(preview_parent) && exist(preview_parent, 'dir') == 0
    mkdir(preview_parent);
end
if exist(preview_file, 'file') ~= 0
    delete(preview_file);
end

model_tag = 'WebPreviewModel';
try
    ModelUtil.remove(model_tag);
catch
end

mphstart(server_host, server_port);
model = mphopen(mph_file, model_tag);
cleanup_guard = onCleanup(@() cleanup_model(model_tag)); %#ok<NASGU>

exported = false;
result_error = '';
try
    result_tags = model.result.tags;
    if ~isempty(result_tags)
        if iscell(result_tags)
            plot_group_tag = char(result_tags{1});
        else
            plot_group_tag = char(result_tags(1));
        end
        export_tag = 'web_preview_image';
        try
            model.result.export.remove(export_tag);
        catch
        end
        model.result.export.create(export_tag, 'Image');
        model.result.export(export_tag).set('plotgroup', plot_group_tag);
        model.result.export(export_tag).set('pngfilename', preview_file);
        model.result.export(export_tag).run;
        exported = exist(preview_file, 'file') ~= 0;
    end
catch ME
    result_error = ME.message;
end

if ~exported
    preview_figure = [];
    try
        geometry_tags = model.geom.tags;
        if isempty(geometry_tags)
            error('COMSOLPreview:NoGeometry', 'The model contains no geometry.');
        end
        if iscell(geometry_tags)
            geometry_tag = char(geometry_tags{1});
        else
            geometry_tag = char(geometry_tags(1));
        end
        preview_figure = figure('Visible', 'off', 'Color', 'white');
        mphgeom(model, geometry_tag);
        axis equal;
        print(preview_figure, preview_file, '-dpng', '-r160');
        close(preview_figure);
        exported = exist(preview_file, 'file') ~= 0;
    catch ME
        if ~isempty(preview_figure)
            try
                close(preview_figure);
            catch
            end
        end
        if isempty(result_error)
            error('COMSOLPreview:ExportFailed', 'Preview export failed: %s', ME.message);
        end
        error('COMSOLPreview:ExportFailed', ...
            'Result export failed: %s | Geometry export failed: %s', ...
            result_error, ME.message);
    end
end

if ~exported
    error('COMSOLPreview:MissingOutput', 'COMSOL did not create the preview image.');
end

fprintf('COMSOL_PREVIEW_PNG=%s\n', preview_file);
end


function cleanup_model(model_tag)
import com.comsol.model.util.*
try
    ModelUtil.remove(model_tag);
catch
end
try
    ModelUtil.disconnect;
catch
end
end
