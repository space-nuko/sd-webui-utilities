import unittest
import import_to_hydrus
from pprint import pp
import json

class ImportToHydrusTest(unittest.TestCase):
    def test_parses_break(self):
        infotext = """masterpiece
BREAK
1girl
BREAK
((outdoors)), egyptian,
Negative prompt: lowres
Steps: 24, Sampler: DPM++ SDE Karras, CFG scale: 7, Seed: 1, Size: 512x768, Model hash: 0873291ac5, Model: AbyssOrangeMix2_nsfw, Clip skip: 2, ENSD: 31337
        """

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'1girl',
             'cfg_scale:7',
             'clip_skip:2',
             'egyptian',
             'ensd:31337',
             'masterpiece',
             'model:abyssorangemix2_nsfw',
             'model_hash:0873291ac5',
             'negative:lowres',
             'outdoors',
             'sampler:dpm++_sde_karras',
             'seed:1',
             'size:512x768',
             'steps:24'})

        self.assertEqual(positive, """masterpiece
BREAK
1girl
BREAK
((outdoors)), egyptian,""")
        self.assertEqual(negative, "lowres")

    def test_parses_and(self):
        infotext = """masterpiece, 1girl
AND
(best quality), white background
Negative prompt: (worst quality, low quality:1.3)
Steps: 30, Sampler: DPM++ 2M Karras, CFG scale: 3, Seed: 988597816, Size: 512x832, Model hash: 2919efc7cc, Model: AOM2-nutmegmixGav2+ElysV3, Batch size: 8, Batch pos: 3, Clip skip: 2, ENSD: 31334
        """

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'1girl',
             'batch_pos:3',
             'batch_size:8',
             'best_quality',
             'cfg_scale:3',
             'clip_skip:2',
             'ensd:31334',
             'masterpiece',
             'model:aom2-nutmegmixgav2+elysv3',
             'model_hash:2919efc7cc',
             'negative:(worst quality, low quality:1.3)',
             'sampler:dpm++_2m_karras',
             'seed:988597816',
             'size:512x832',
             'steps:30',
             'uses_multicond:true',
             'white_background'})

        self.assertEqual(positive, """masterpiece, 1girl
AND
(best quality), white background""")
        self.assertEqual(negative, "(worst quality, low quality:1.3)")


    def test_parses_dynamic_prompt_templates(self):
        infotext = """1girl, pink hair
Negative prompt: (worst quality, low quality:1.4)
Steps: 20, Sampler: DPM++ SDE Karras, CFG scale: 6, Seed: 780207036, Size: 512x768, Model hash: 0873291ac5, Model: AbyssOrangeMix2_nsfw, Denoising strength: 0.2, ENSD: 31337, Mask blur: 1, SD upscale overlap: 64, SD upscale upscaler: 4x_Valar_v1, AddNet Enabled: True, AddNet Module 1: LoRA, AddNet Model 1: ElysiaV3-000002(6d3eb064dcc1), AddNet Weight A 1: 0.9, AddNet Weight B 1: 0.9, AddNet Module 2: LoRA, AddNet Model 2: elfmorie2(a34cd9a8c3cc), AddNet Weight A 2: 1, AddNet Weight B 2: 1
Template: 1girl, __haircolor__
Negative Template: (worst quality, low quality:1.4), __badprompt__
        """

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'1girl',
             'addnet_enabled:true',
             'addnet_model:elfmorie2(a34cd9a8c3cc)',
             'addnet_model:elysiav3-000002(6d3eb064dcc1)',
             'addnet_model_hash:6d3eb064dcc1',
             'addnet_model_hash:a34cd9a8c3cc',
             'addnet_model_name:elfmorie2',
             'addnet_model_name:elysiav3-000002',
             'cfg_scale:6',
             'denoising_strength:0.2',
             'ensd:31337',
             'mask_blur:1',
             'model:abyssorangemix2_nsfw',
             'model_hash:0873291ac5',
             'negative:(worst quality, low quality:1.4)',
             'pink_hair',
             'sampler:dpm++_sde_karras',
             'sd_upscale_overlap:64',
             'sd_upscale_upscaler:4x_valar_v1',
             'seed:780207036',
             'size:512x768',
             'steps:20'})
        self.assertEqual(positive, "1girl, pink hair")
        self.assertEqual(negative, "(worst quality, low quality:1.4)")


    def test_parses_xyz_grid(self):
        infotext = """1girl
Negative prompt: (worst quality, low quality:1.4)
Steps: 20, Sampler: DPM++ SDE Karras, CFG scale: 5, Seed: 1964718363, Size: 512x512, Model hash: 736a6f43c2, Denoising strength: 0.5, Clip skip: 2, Hires upscale: 1.75, Hires steps: 14, Hires upscaler: Latent (nearest-exact), Script: X/Y/Z plot, X Type: Prompt S/R, X Values: "<lora:cru5rb:0.5> , <lora:cru5rb:0.6>,<lora:cru5rb:0.7>,  <lora:cru5rb:0.8> ,<lora:cru5rb:0.9> , <lora:cru5rb:1>,"
        """

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'1girl',
             'cfg_scale:5',
             'clip_skip:2',
             'denoising_strength:0.5',
             'extra_networks_lora:cru5rb',
             'hires_steps:14',
             'hires_upscale:1.75',
             'hires_upscaler:latent_(nearest-exact)',
             'model_hash:736a6f43c2',
             'negative:(worst quality, low quality:1.4)',
             'sampler:dpm++_sde_karras',
             'script:x/y/z_plot',
             'seed:1964718363',
             'size:512x512',
             'steps:20',
             'x_type:prompt_s/r'})
        self.assertEqual(positive, "1girl")
        self.assertEqual(negative, "(worst quality, low quality:1.4)")

    def test_parses_extra_networks(self):
        infotext = """(colorful:1.3),
dreamlike fantasy landscape where everything is a shade of pink,
 <lora:NAI-cutesexyrobutts:1>
Negative prompt: (worst quality:1.4), (low quality:1.4) , (monochrome:1.1)
Steps: 40, Sampler: DPM++ 2M Karras, CFG scale: 12, Seed: 2416682767, Size: 640x512, Model hash: 0f0eaaa61e, Model: pastelmix-better-vae-fp16, Denoising strength: 0.55, Clip skip: 2, ENSD: 31337, Hires upscale: 2, Hires steps: 20, Hires upscaler: Latent
"""

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'cfg_scale:12',
            'clip_skip:2',
            'colorful',
            'denoising_strength:0.55',
            'dreamlike_fantasy_landscape_where_everything_is_a_shade_of_pink',
            'extra_networks_lora:NAI-cutesexyrobutts',
            'ensd:31337',
            'hires_steps:20',
            'hires_upscale:2',
            'hires_upscaler:latent',
            'model:pastelmix-better-vae-fp16',
            'model_hash:0f0eaaa61e',
            'negative:(worst quality:1.4), (low quality:1.4) , (monochrome:1.1)',
            'sampler:dpm++_2m_karras',
            'seed:2416682767',
            'size:640x512',
            'steps:40'})
        self.assertEqual(positive, """(colorful:1.3),
dreamlike fantasy landscape where everything is a shade of pink,
 <lora:NAI-cutesexyrobutts:1>""")
        self.assertEqual(negative, "(worst quality:1.4), (low quality:1.4) , (monochrome:1.1)")

    def test_strips_wildcard_prompt(self):
        infotext = """1girl
Negative prompt: lowres, bad anatomy
Steps: 40, Sampler: DPM++ 2M Karras, CFG scale: 9, Seed: 2976004442, Size: 576x512, Model hash: 931f9552, Model: AbyssOrangeMix2_hard, Batch size: 2, Batch pos: 0, Denoising strength: 0.6, Clip skip: 2, ENSD: 31337, Wildcard prompt: "[:((beautiful detailed eyes)), (beautiful detailed face), :0.7][:(perfect detailed hands and fingers, detailed hands+fingers:1.1):0.45]masterpiece, best quality, highres, absurdres, world masterpiece theater, impressionism, intricate, ambient light, [sfw:nsfw:0.33], (1girl), (solo), solo focus, from above, looking up at viewer, close-up, (carry me, incoming hug, outstretched arms, reaching towards viewer:1.05)
(a young girl with a naughty smile drenched in the rain on the sidewalk of a futuristic city and neon signs reflected in puddles), ((long white summer dress, detailed fabric)), (wet fabric, wet skin, shiny skin, rain, wet)[:, see-through dress:0.85], {strapless dress|sleeveless dress|off-shoulder dress}, (side slit dress:0.9), (downblouse, nipples), (perfect cute little teen ass:1.1), (medium breasts:1)[:, small nipples:0.1], (slender waist:0.9), athletic, fit, {medium|long|very long} hair, {75%blonde|chestnut hair, red|chestnut red} hair,{{ponytail|high ponytail|twintails}|{french braid|single braid|crown braid**,crown**|side_braid}|50% }, {|33%(freckles:0.85), }{75%blue|green} eyes, black_eyeliner, sideswept hair{|20%, hair ornament}, [(little girl:1.15), (child:1.2), (perfect anatomy:1.2):, little girl, child:0.25]
(Daniel F. Gerhartz:1.1), (Sally Mann:0.9), (Henry Ascencio:1.1), (Emile Vernon:1.1), (Tom Bagshaw:1.1), (Krenz Cushart:1.2)", File includes: , Hires resize: 1152x1024, Hires upscaler: Latent (nearest-exact), Discard penultimate sigma: True
        """

        tags, positive, negative = import_to_hydrus.parse_a1111_prompt(infotext)

        self.assertEqual(tags,
            {'1girl',
            'batch_pos:0',
            'batch_size:2',
            'cfg_scale:9',
            'clip_skip:2',
            'denoising_strength:0.6',
            'discard_penultimate_sigma:true',
            'ensd:31337',
            'file_includes:',
            'hires_resize:1152x1024',
            'hires_upscaler:latent_(nearest-exact)',
            'model:abyssorangemix2_hard',
            'model_hash:931f9552',
            'negative:lowres, bad anatomy',
            'sampler:dpm++_2m_karras',
            'seed:2976004442',
            'size:576x512',
            'steps:40'})
        self.assertEqual(positive, "1girl")
        self.assertEqual(negative, "lowres, bad anatomy")

    def test_imports_nai(self):
        metadata = '{"Description": "{artist:nishikasai munieru}, 1girl, barefoot, solo, spread toes, soles, night, lamp, on bed, bedroom, moody, knees together, best quality, amazing quality, very aesthetic, absurdres", "Software": "NovelAI", "Source": "Stable Diffusion XL C1E1DE52", "Generation time": "12.132191160926595", "Comment": "{\\"prompt\\": \\"nishikasai munieru, 1girl, barefoot, solo, spread toes, soles, night, lamp, on bed, bedroom, moody, knees together, best quality, amazing quality, very aesthetic, absurdres\\", \\"steps\\": 28, \\"height\\": 1856, \\"width\\": 1280, \\"scale\\": 5.0, \\"uncond_scale\\": 1.0, \\"cfg_rescale\\": 0.0, \\"seed\\": 2668694883, \\"n_samples\\": 1, \\"hide_debug_overlay\\": false, \\"noise_schedule\\": \\"native\\", \\"sampler\\": \\"k_euler\\", \\"controlnet_strength\\": 1.0, \\"controlnet_model\\": null, \\"dynamic_thresholding\\": false, \\"dynamic_thresholding_percentile\\": 0.999, \\"dynamic_thresholding_mimic_scale\\": 10.0, \\"sm\\": false, \\"sm_dyn\\": false, \\"skip_cfg_below_sigma\\": 0.0, \\"lora_unet_weights\\": null, \\"lora_clip_weights\\": null, \\"strength\\": 0.5, \\"noise\\": 0.0, \\"extra_noise_seed\\": 2668694883, \\"legacy\\": false, \\"uc\\": \\"nsfw, lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], worst quality, low quality, artist name, signature, watermark\\", \\"request_type\\": \\"Img2ImgRequest\\"}"}'

        result = json.loads(metadata)
        tags, positive, negative = import_to_hydrus.parse_nai_prompt(result)

        self.assertEqual(tags,
            {'very_aesthetic',
            'amazing_quality',
            'soles',
            'night',
            'seed:2668694883',
            'knees_together',
            'scale:5.0',
            'controlnet_strength:1.0',
            'noise_schedule:native',
            'extra_noise_seed:2668694883',
            'request_type:Img2ImgRequest',
            'cfg_rescale:0.0',
            'sampler:k_euler',
            'sm:false',
            'negative:nsfw, lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], worst quality, low quality, artist name, signature, watermark',
            'uncond_scale:1.0',
            '1girl',
            'skip_cfg_below_sigma:0.0',
            'on_bed',
            'absurdres',
            'dynamic_thresholding:false',
            'controlnet_model:null',
            'lamp',
            'spread_toes',
            'n_samples:1',
            'legacy:false',
            'dynamic_thresholding_percentile:0.999',
            'best_quality',
            'barefoot',
            'sm_dyn:false',
            'bedroom',
            'steps:28',
            'lora_clip_weights:null',
            'noise:0.0',
            'artist;nishikasai_munieru',
            'dynamic_thresholding_mimic_scale:10.0',
            'strength:0.5',
            'solo',
            'hide_debug_overlay:false',
            'lora_unet_weights:null',
            'moody',
            'naiv3_source:Stable Diffusion XL C1E1DE52',
            'naiv3_software:NovelAI'})
        self.assertEqual(positive, "{artist:nishikasai munieru}, 1girl, barefoot, solo, spread toes, soles, night, lamp, on bed, bedroom, moody, knees together, best quality, amazing quality, very aesthetic, absurdres")
        self.assertEqual(negative, "nsfw, lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], worst quality, low quality, artist name, signature, watermark")
