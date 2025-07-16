def write_my_csv(input_pd, output_path):
    input_pd.to_csv(output_path, index='False')