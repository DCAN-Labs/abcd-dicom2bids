%% variable initialization

clear variables
load mapping.mat

QC_file = 'spreadsheets/DAL_ABCD_QC_merged_pcqcinfo.csv';
image03_file = 'spreadsheets/image03.txt';
output_csv = 'spreadsheets/ABCD_good_and_bad_series_table.csv';

%% QC parsing

data = DAL_ABCD_merged_pcqcinfo_importer(QC_file);

for i = 1:height(data) 
    if data.SeriesTime(i) < 100000 
        data.timestamp{i} = ['0' num2str(floor(data.SeriesTime(i)))];
    else
        data.timestamp{i} = num2str(floor(data.SeriesTime(i)));
    end
end
data.CleanFlag = cleandata_idx;

%% image03 parsing

image03 = image03_importer(image03_file);

for i = 1:height(image03)
    image03.timestamp{i} = image03.image_file{i}(end-10:end-5);
end

image03_1 = innerjoin(image03,map_image03_qc);
image03_2 = innerjoin(image03_1,map_image03_descriptor);

image03_2 = sortrows(image03_2,'image_file','ascend');
image03_2.Properties.VariableNames{1} = 'pGUID';
image03_2.Properties.VariableNames{9} = 'EventName';

%% table joins

data_1 = innerjoin(data,map_qc_descriptor);
data_1 = sortrows(data_1,'pGUID','ascend');

% Hack to deal with quotations around strings in table
foo = image03_2.SeriesType;
[l,w] = size(foo);
for i=1:l
    foo(i) = strjoin(['"' string(foo(i)) '"'],'');
end
image03_2.SeriesType = foo;

data_2 = innerjoin(data_1,image03_2);


%% final output table (path hardcoded)

writetable(data_2,output_csv);

