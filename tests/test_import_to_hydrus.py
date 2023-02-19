import unittest
import import_to_hydrus
from pprint import pp

class ImportToHydrusTest(unittest.TestCase):
    def test_parses_extra_networks(self):
        infotext = """(colorful:1.3),
dreamlike fantasy landscape where everything is a shade of pink,
 <lora:NAI-cutesexyrobutts:1>
Negative prompt: (worst quality:1.4), (low quality:1.4) , (monochrome:1.1)
Steps: 40, Sampler: DPM++ 2M Karras, CFG scale: 12, Seed: 2416682767, Size: 640x512, Model hash: 0f0eaaa61e, Model: pastelmix-better-vae-fp16, Denoising strength: 0.55, Clip skip: 2, ENSD: 31337, Hires upscale: 2, Hires steps: 20, Hires upscaler: Latent
"""

        tags = import_to_hydrus.get_tags_from_pnginfo(infotext)

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

    def test_strips_wildcard_prompt(self):
        infotext = """1girl
Negative prompt: lowres, bad anatomy
Steps: 40, Sampler: DPM++ 2M Karras, CFG scale: 9, Seed: 2976004442, Size: 576x512, Model hash: 931f9552, Model: AbyssOrangeMix2_hard, Batch size: 2, Batch pos: 0, Denoising strength: 0.6, Clip skip: 2, ENSD: 31337, Wildcard prompt: "[:((beautiful detailed eyes)), (beautiful detailed face), :0.7][:(perfect detailed hands and fingers, detailed hands+fingers:1.1):0.45]masterpiece, best quality, highres, absurdres, world masterpiece theater, impressionism, intricate, ambient light, [sfw:nsfw:0.33], (1girl), (solo), solo focus, from above, looking up at viewer, close-up, (carry me, incoming hug, outstretched arms, reaching towards viewer:1.05)
(a young girl with a naughty smile drenched in the rain on the sidewalk of a futuristic city and neon signs reflected in puddles), ((long white summer dress, detailed fabric)), (wet fabric, wet skin, shiny skin, rain, wet)[:, see-through dress:0.85], {strapless dress|sleeveless dress|off-shoulder dress}, (side slit dress:0.9), (downblouse, nipples), (perfect cute little teen ass:1.1), (medium breasts:1)[:, small nipples:0.1], (slender waist:0.9), athletic, fit, {medium|long|very long} hair, {75%blonde|chestnut hair, red|chestnut red} hair,{{ponytail|high ponytail|twintails}|{french braid|single braid|crown braid**,crown**|side_braid}|50% }, {|33%(freckles:0.85), }{75%blue|green} eyes, black_eyeliner, sideswept hair{|20%, hair ornament}, [(little girl:1.15), (child:1.2), (perfect anatomy:1.2):, little girl, child:0.25]
(Daniel F. Gerhartz:1.1), (Sally Mann:0.9), (Henry Ascencio:1.1), (Emile Vernon:1.1), (Tom Bagshaw:1.1), (Krenz Cushart:1.2)", File includes: , Hires resize: 1152x1024, Hires upscaler: Latent (nearest-exact), Discard penultimate sigma: True
        """

        tags = import_to_hydrus.get_tags_from_pnginfo(infotext)

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
