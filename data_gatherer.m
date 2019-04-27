%%
clear variables
load mapping.mat

DAL_ABCD_merged_pcqcinfo_importer;

for i = 1:height(data) 
    if data.SeriesTime(i) < 100000 
        data.timestamp{i} = ['0' num2str(floor(data.SeriesTime(i)))];
    else
        data.timestamp{i} = num2str(floor(data.SeriesTime(i)));
    end
end
data.CleanFlag = cleandata_idx;

%%
image03_importer;
for i = 1:height(image03)
    image03.timestamp{i} = image03.image_file{i}(end-10:end-5);
end

image03_1 = innerjoin(image03,map_image03_qc);
image03_2 = innerjoin(image03_1,map_image03_descriptor);

image03_2 = sortrows(image03_2,'image_file','ascend');
image03_2.Properties.VariableNames{1} = 'pGUID';
image03_2.Properties.VariableNames{9} = 'EventName';

%%
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


%%
writetable(data_2,'./spreadsheets/ABCD_good_and_bad_series_table.csv');

